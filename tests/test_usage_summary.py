from types import SimpleNamespace

import pytest
from pydantic import BaseModel

from config.settings import AppSettings, RuntimeTuning
from core.llm import litellm_client
from core.llm.litellm_client import LiteLLMService


def test_usage_summary_aggregates_records() -> None:
    service = LiteLLMService(AppSettings())
    response = SimpleNamespace(
        usage=SimpleNamespace(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=15,
            prompt_tokens_details=SimpleNamespace(cached_tokens=2),
        )
    )
    service._record_response(operation="unit", model="deepseek/deepseek-chat", response=response)
    summary = service.usage_summary()

    assert summary.calls == 1
    assert summary.prompt_tokens == 10
    assert summary.cached_tokens == 2
    assert "deepseek/deepseek-chat" in summary.by_model


class ServerDisconnectedError(Exception):
    pass


@pytest.mark.asyncio
async def test_complete_text_retries_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    async def fake_acompletion(**kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ServerDisconnectedError("Server disconnected")
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="重试成功"))],
            usage=SimpleNamespace(
                prompt_tokens=12,
                completion_tokens=8,
                total_tokens=20,
                prompt_tokens_details=SimpleNamespace(cached_tokens=0),
            ),
        )

    monkeypatch.setattr(litellm_client, "acompletion", fake_acompletion)
    service = LiteLLMService(
        AppSettings(
            tuning=RuntimeTuning(
                llm_retry_attempts=2,
                llm_retry_backoff_seconds=0,
            )
        )
    )

    response = await service.complete_text(
        model="deepseek/deepseek-chat",
        messages=[{"role": "user", "content": "test"}],
    )

    assert response.text == "重试成功"
    assert calls == 2
    assert service.usage_summary().calls == 1


@pytest.mark.asyncio
async def test_complete_text_uses_responses_wire_api(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    async def fake_aresponses(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            output_text="OK",
            usage=SimpleNamespace(input_tokens=7, output_tokens=2, total_tokens=9),
        )

    monkeypatch.setattr(litellm_client, "aresponses", fake_aresponses)
    service = LiteLLMService(
        AppSettings(
            runtime_api_base_url="https://api.clawto.link",
            runtime_api_key="sk-test",
            runtime_wire_api="responses",
        )
    )

    response = await service.complete_text(
        model="gpt-5.5",
        messages=[{"role": "user", "content": "只回复 OK"}],
    )

    assert response.text == "OK"
    assert captured["api_base"] == "https://api.clawto.link"
    assert captured["api_key"] == "sk-test"
    assert captured["custom_llm_provider"] == "openai"
    assert "base_url" not in captured
    assert response.usage.prompt_tokens == 7
    assert response.usage.completion_tokens == 2


class StructuredProbe(BaseModel):
    answer: str


@pytest.mark.asyncio
async def test_complete_structured_uses_responses_text_format(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    async def fake_aresponses(**kwargs):
        captured.update(kwargs)
        return SimpleNamespace(
            output_text='{"answer":"OK"}',
            usage=SimpleNamespace(input_tokens=8, output_tokens=4, total_tokens=12),
        )

    monkeypatch.setattr(litellm_client, "aresponses", fake_aresponses)
    service = LiteLLMService(
        AppSettings(
            runtime_api_base_url="https://api.clawto.link",
            runtime_api_key="sk-test",
            runtime_wire_api="responses",
        )
    )

    response = await service.complete_structured(
        model="gpt-5.5",
        messages=[{"role": "user", "content": "返回 JSON"}],
        response_model=StructuredProbe,
    )

    assert response == StructuredProbe(answer="OK")
    assert captured["text_format"] is StructuredProbe
