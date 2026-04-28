from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Awaitable, Callable, TypeVar

import instructor
from litellm import acompletion, aresponses, completion_cost
from pydantic import BaseModel, Field

from config.settings import AppSettings


Message = dict[str, str]
ResponseT = TypeVar("ResponseT")
_TRANSIENT_ERROR_TYPES = {
    "APIConnectionError",
    "APITimeoutError",
    "InternalServerError",
    "RateLimitError",
    "ReadError",
    "RemoteProtocolError",
    "ServerDisconnectedError",
    "ServiceUnavailableError",
    "Timeout",
}
_TRANSIENT_ERROR_KEYWORDS = (
    "connection aborted",
    "connection reset",
    "gateway timeout",
    "internal server error",
    "rate limit",
    "read timed out",
    "remoteprotocolerror",
    "server disconnected",
    "service unavailable",
    "temporarily unavailable",
    "timeout",
    "timed out",
    "too many requests",
)


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0


class LLMTextResponse(BaseModel):
    text: str
    usage: LLMUsage = Field(default_factory=LLMUsage)
    cost_usd: float = 0.0


class LLMCallRecord(BaseModel):
    timestamp: datetime
    operation: str
    model: str
    usage: LLMUsage
    cost_usd: float = 0.0


class LLMUsageSummary(BaseModel):
    calls: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cached_tokens: int = 0
    total_cost_usd: float = 0.0
    by_model: dict[str, dict[str, float | int]] = Field(default_factory=dict)


class LiteLLMService:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self._structured_client = instructor.from_litellm(acompletion)
        self._records: list[LLMCallRecord] = []

    def _default_provider_kwargs(self, model: str) -> dict[str, Any]:
        if model.startswith("deepseek/") and self.settings.deepseek_api_key:
            return {
                "api_key": self.settings.deepseek_api_key,
                "base_url": self.settings.models.deepseek_base_url,
            }
        if model.startswith("openai/") and self.settings.openai_api_key:
            return {
                "api_key": self.settings.openai_api_key,
            }
        return {}

    def _provider_kwargs(self, model: str) -> dict[str, Any]:
        default_kwargs = self._default_provider_kwargs(model)
        runtime_base_url = (self.settings.runtime_api_base_url or "").strip()
        runtime_api_key = (self.settings.runtime_api_key or "").strip()
        if not runtime_base_url and not runtime_api_key:
            return default_kwargs

        runtime_kwargs = dict(default_kwargs)
        if runtime_api_key:
            runtime_kwargs["api_key"] = runtime_api_key
        if runtime_base_url:
            runtime_kwargs["base_url"] = runtime_base_url
        return runtime_kwargs

    def _request_kwargs(self, model: str) -> dict[str, Any]:
        return {
            "timeout": self.settings.tuning.llm_request_timeout_seconds,
            "num_retries": 0,
            **self._provider_kwargs(model),
        }

    def _responses_request_kwargs(self, model: str) -> dict[str, Any]:
        kwargs = {
            "timeout": self.settings.tuning.llm_request_timeout_seconds,
            **self._provider_kwargs(model),
        }
        base_url = kwargs.pop("base_url", None)
        if base_url:
            kwargs["api_base"] = base_url
        kwargs.setdefault("custom_llm_provider", "openai")
        return kwargs

    @staticmethod
    def _responses_input(messages: list[Message]) -> list[Message]:
        return [{"role": item["role"], "content": item["content"]} for item in messages]

    def _is_transient_error(self, error: Exception) -> bool:
        current: BaseException | None = error
        while current is not None:
            if current.__class__.__name__ in _TRANSIENT_ERROR_TYPES:
                return True
            message = str(current).lower()
            if any(keyword in message for keyword in _TRANSIENT_ERROR_KEYWORDS):
                return True
            current = current.__cause__ or current.__context__
        return False

    async def _retry_async(
        self,
        *,
        call: Callable[[], Awaitable[ResponseT]],
    ) -> ResponseT:
        delay = max(0.0, self.settings.tuning.llm_retry_backoff_seconds)
        attempts = max(1, self.settings.tuning.llm_retry_attempts)
        last_error: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                return await call()
            except Exception as error:
                last_error = error
                if attempt >= attempts or not self._is_transient_error(error):
                    raise
                await asyncio.sleep(delay * attempt if delay else 0.0)
        assert last_error is not None
        raise last_error

    @staticmethod
    def _extract_usage(response: Any) -> LLMUsage:
        usage = getattr(response, "usage", None)
        prompt_details = getattr(usage, "prompt_tokens_details", None) if usage else None
        prompt_details = prompt_details or (getattr(usage, "input_tokens_details", None) if usage else None)
        cached_tokens = getattr(prompt_details, "cached_tokens", 0) if prompt_details else 0
        return LLMUsage(
            prompt_tokens=(getattr(usage, "prompt_tokens", None) or getattr(usage, "input_tokens", 0) or 0),
            completion_tokens=(
                getattr(usage, "completion_tokens", None) or getattr(usage, "output_tokens", 0) or 0
            ),
            total_tokens=getattr(usage, "total_tokens", 0) or 0,
            cached_tokens=cached_tokens or 0,
        )

    @staticmethod
    def _extract_responses_text(response: Any) -> str:
        output_text = getattr(response, "output_text", None)
        if isinstance(output_text, str):
            return output_text.strip()
        return str(response).strip()

    def _record_response(
        self,
        *,
        operation: str,
        model: str,
        response: Any,
    ) -> tuple[LLMUsage, float]:
        usage = self._extract_usage(response)
        try:
            cost = float(completion_cost(completion_response=response))
        except Exception:
            cost = 0.0

        self._records.append(
            LLMCallRecord(
                timestamp=datetime.now(timezone.utc),
                operation=operation,
                model=model,
                usage=usage,
                cost_usd=cost,
            )
        )
        return usage, cost

    def usage_mark(self) -> int:
        return len(self._records)

    def usage_summary(
        self,
        start_index: int = 0,
        end_index: int | None = None,
    ) -> LLMUsageSummary:
        records = self._records[start_index:end_index]
        summary = LLMUsageSummary(calls=len(records))
        for record in records:
            summary.prompt_tokens += record.usage.prompt_tokens
            summary.completion_tokens += record.usage.completion_tokens
            summary.total_tokens += record.usage.total_tokens
            summary.cached_tokens += record.usage.cached_tokens
            summary.total_cost_usd += record.cost_usd

            bucket = summary.by_model.setdefault(
                record.model,
                {
                    "calls": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                    "total_tokens": 0,
                    "cached_tokens": 0,
                    "total_cost_usd": 0.0,
                },
            )
            bucket["calls"] = int(bucket["calls"]) + 1
            bucket["prompt_tokens"] = int(bucket["prompt_tokens"]) + record.usage.prompt_tokens
            bucket["completion_tokens"] = int(bucket["completion_tokens"]) + record.usage.completion_tokens
            bucket["total_tokens"] = int(bucket["total_tokens"]) + record.usage.total_tokens
            bucket["cached_tokens"] = int(bucket["cached_tokens"]) + record.usage.cached_tokens
            bucket["total_cost_usd"] = float(bucket["total_cost_usd"]) + record.cost_usd

        summary.total_cost_usd = round(summary.total_cost_usd, 6)
        for bucket in summary.by_model.values():
            bucket["total_cost_usd"] = round(float(bucket["total_cost_usd"]), 6)
        return summary

    async def complete_text(
        self,
        *,
        model: str,
        messages: list[Message],
        temperature: float = 0.7,
        max_tokens: int | None = None,
        operation: str = "general",
        **kwargs: Any,
    ) -> LLMTextResponse:
        if self.settings.runtime_wire_api == "responses":
            response = await self._retry_async(
                call=lambda: aresponses(
                    model=model,
                    input=self._responses_input(messages),
                    temperature=temperature,
                    max_output_tokens=max_tokens or self.settings.models.max_tokens,
                    **self._responses_request_kwargs(model),
                    **kwargs,
                )
            )
            usage, cost = self._record_response(
                operation=operation,
                model=model,
                response=response,
            )
            return LLMTextResponse(
                text=self._extract_responses_text(response),
                usage=usage,
                cost_usd=cost,
            )

        response = await self._retry_async(
            call=lambda: acompletion(
                model=model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens or self.settings.models.max_tokens,
                **self._request_kwargs(model),
                **kwargs,
            )
        )
        content = response.choices[0].message.content or ""
        usage, cost = self._record_response(
            operation=operation,
            model=model,
            response=response,
        )
        return LLMTextResponse(text=content.strip(), usage=usage, cost_usd=cost)

    async def complete_structured(
        self,
        *,
        model: str,
        messages: list[Message],
        response_model: type[BaseModel],
        temperature: float = 0.3,
        max_tokens: int | None = None,
        operation: str = "structured",
        **kwargs: Any,
    ) -> BaseModel:
        if self.settings.runtime_wire_api == "responses":
            response = await self._retry_async(
                call=lambda: aresponses(
                    model=model,
                    input=self._responses_input(messages),
                    temperature=temperature,
                    max_output_tokens=max_tokens or self.settings.models.max_tokens,
                    text_format=response_model,
                    **self._responses_request_kwargs(model),
                    **kwargs,
                )
            )
            self._record_response(operation=operation, model=model, response=response)
            return response_model.model_validate_json(self._extract_responses_text(response))

        try:
            parsed, raw = await self._retry_async(
                call=lambda: self._structured_client.chat.completions.create_with_completion(
                    model=model,
                    messages=messages,
                    response_model=response_model,
                    temperature=temperature,
                    max_tokens=max_tokens or self.settings.models.max_tokens,
                    max_retries=2,
                    **self._request_kwargs(model),
                    **kwargs,
                )
            )
            self._record_response(operation=operation, model=model, response=raw)
            return parsed
        except Exception as error:
            if self._is_transient_error(error):
                raise
            schema_hint = json.dumps(
                response_model.model_json_schema(),
                ensure_ascii=False,
                indent=2,
            )
            fallback_messages = list(messages)
            fallback_messages.append(
                {
                    "role": "user",
                    "content": (
                        "请仅返回一个严格 JSON 对象，必须匹配以下 JSON Schema，"
                        f"不要输出任何额外文本。\n{schema_hint}"
                    ),
                }
            )
            raw = await self.complete_text(
                model=model,
                messages=fallback_messages,
                temperature=temperature,
                max_tokens=max_tokens,
                response_format={"type": "json_object"},
                operation=f"{operation}_fallback",
                **kwargs,
            )
            return response_model.model_validate_json(raw.text)
