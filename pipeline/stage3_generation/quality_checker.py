from __future__ import annotations

import asyncio
from typing import Any

from deepeval.metrics import GEval
from deepeval.models import DeepEvalBaseLLM
from deepeval.test_case import LLMTestCase, LLMTestCaseParams
from pydantic import BaseModel, Field

from config.settings import AppSettings
from core.llm.litellm_client import LiteLLMService
from core.models.skeleton import ChapterSkeleton


class QualityReport(BaseModel):
    score: float
    verdict: str
    issues: list[str] = Field(default_factory=list)
    used_deepeval: bool = False


class LiteLLMDeepEvalModel(DeepEvalBaseLLM):
    def __init__(self, llm_service: LiteLLMService, model: str):
        self.llm_service = llm_service
        self._model = model
        super().__init__(model=model)

    def load_model(self, *args, **kwargs) -> "LiteLLMDeepEvalModel":
        return self

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return asyncio.run(self.a_generate(prompt, **kwargs))

    async def a_generate(self, prompt: str, schema=None, **kwargs: Any) -> str:
        if schema is not None:
            structured = await self.llm_service.complete_structured(
                model=self._model,
                messages=[{"role": "user", "content": prompt}],
                response_model=schema,
                temperature=0.1,
            )
            return structured.model_dump_json()
        response = await self.llm_service.complete_text(
            model=self._model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1024,
            operation="stage3_quality_eval",
        )
        return response.text

    def get_model_name(self, *args, **kwargs) -> str:
        return self._model

    def supports_structured_outputs(self) -> bool | None:
        return True


class QualityChecker:
    def __init__(self, settings: AppSettings, llm_service: LiteLLMService):
        self.settings = settings
        self.llm_service = llm_service

    async def evaluate(
        self,
        *,
        skeleton: ChapterSkeleton,
        draft_text: str,
        style_samples: list[str],
    ) -> QualityReport:
        try:
            metric = GEval(
                name="续写一致性",
                evaluation_params=[
                    LLMTestCaseParams.INPUT,
                    LLMTestCaseParams.ACTUAL_OUTPUT,
                    LLMTestCaseParams.CONTEXT,
                ],
                criteria=(
                    "正文是否覆盖骨架要求，角色行为是否自洽，是否维持中文网文的连贯推进，"
                    "并且至少推进一个核心伏笔。"
                ),
                model=LiteLLMDeepEvalModel(
                    self.llm_service,
                    self.settings.models.quality_model,
                ),
                threshold=self.settings.tuning.quality_threshold,
                async_mode=True,
                verbose_mode=False,
            )
            test_case = LLMTestCase(
                input=skeleton.model_dump_json(),
                actual_output=draft_text,
                context=style_samples,
            )
            score = await metric.a_measure(test_case)
            verdict = "pass" if score >= self.settings.tuning.quality_threshold else "revise"
            issues = [metric.reason] if getattr(metric, "reason", None) else []
            return QualityReport(
                score=score,
                verdict=verdict,
                issues=issues,
                used_deepeval=True,
            )
        except Exception:
            issues: list[str] = []
            skeleton_people = {
                name
                for scene in skeleton.scenes
                for name in scene.participants
                if name.strip()
            }
            if len(draft_text) < 800:
                issues.append("正文过短。")
            if skeleton_people and not any(name in draft_text for name in skeleton_people):
                issues.append("正文未覆盖骨架中的主要角色。")
            score = 1.0 if not issues else max(0.2, 1.0 - len(issues) * 0.25)
            verdict = "pass" if score >= self.settings.tuning.quality_threshold else "revise"
            return QualityReport(
                score=score,
                verdict=verdict,
                issues=issues,
                used_deepeval=False,
            )
