from __future__ import annotations

import json

from pydantic import BaseModel, Field

from config.settings import AppSettings
from core.models.chapter_brief import ChapterBrief
from core.models.lorebook import LorebookBundle
from core.llm.litellm_client import LiteLLMService
from core.models.skeleton import AgentConsensusLog, ChapterSkeleton, SceneNode


class ChapterSkeletonDraft(BaseModel):
    chapter_theme: str
    scenes: list[SceneNode] = Field(default_factory=list)
    threads_to_advance: list[str] = Field(default_factory=list)
    threads_to_close: list[str] = Field(default_factory=list)


class SkeletonBuilder:
    def __init__(self, settings: AppSettings, llm_service: LiteLLMService):
        self.settings = settings
        self.llm_service = llm_service

    async def build(
        self,
        *,
        chapter_number: int,
        chapter_goal: str,
        arbitration_result: dict,
        chapter_brief: ChapterBrief | None,
        lorebook_context: LorebookBundle | None,
        focus_thread_ids: list[str],
        consensus_log: list[AgentConsensusLog],
    ) -> ChapterSkeleton:
        lorebook_text = "无"
        if lorebook_context is not None and lorebook_context.hits:
            hit_ids = {item.entry_id for item in lorebook_context.hits}
            selected = [
                entry.model_dump(mode="json")
                for entry in lorebook_context.entries
                if entry.entry_id in hit_ids
            ]
            if selected:
                lorebook_text = json.dumps(selected, ensure_ascii=False, indent=2)
        prompt = (
            "你是章节骨架生成器。请根据仲裁结果，拆出 3-6 个场景。"
            "每个场景都要给出场景类型、参与角色、目的和预计字数。"
            "必须严格输出 JSON。\n\n"
            f"[章节号]\n{chapter_number}\n\n"
            f"[章节目标]\n{chapter_goal}\n\n"
            f"[章节 brief]\n{chapter_brief.model_dump_json(indent=2) if chapter_brief else '无'}\n\n"
            f"[Lorebook 命中]\n{lorebook_text}\n\n"
            f"[必须关注伏笔]\n{focus_thread_ids}\n\n"
            f"[仲裁结果]\n{json.dumps(arbitration_result, ensure_ascii=False, indent=2)}"
        )
        draft = await self.llm_service.complete_structured(
            model=self.settings.models.plot_model,
            messages=[{"role": "user", "content": prompt}],
            response_model=ChapterSkeletonDraft,
            temperature=0.2,
            operation="stage2_build_skeleton",
        )
        normalized_advance = [item for item in draft.threads_to_advance if item in focus_thread_ids]
        normalized_close = [item for item in draft.threads_to_close if item in focus_thread_ids]
        if not normalized_advance and focus_thread_ids:
            normalized_advance = focus_thread_ids[:2]
        return ChapterSkeleton(
            chapter_number=chapter_number,
            chapter_theme=draft.chapter_theme,
            scenes=draft.scenes,
            threads_to_advance=normalized_advance,
            threads_to_close=normalized_close,
            agent_consensus_log=consensus_log,
        )
