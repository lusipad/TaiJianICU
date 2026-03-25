from __future__ import annotations

import json

from config.settings import AppSettings, render_prompt
from core.models.chapter_brief import ChapterBrief
from core.models.lorebook import LorebookBundle
from core.llm.litellm_client import LiteLLMService
from core.models.skeleton import ChapterSkeleton
from core.models.style_profile import StyleProfile
from core.models.world_model import WorldModel


class ChapterGenerator:
    def __init__(self, settings: AppSettings, llm_service: LiteLLMService):
        self.settings = settings
        self.llm_service = llm_service

    @staticmethod
    def _world_context_text(world_model: WorldModel | None) -> str:
        if world_model is None:
            return "无"
        lines: list[str] = []
        if world_model.summary:
            lines.append(f"摘要：{world_model.summary}")
        if world_model.world_tensions:
            lines.append(f"世界张力：{'；'.join(world_model.world_tensions[:3])}")
        if world_model.canon_facts:
            lines.append(
                "不可违背设定："
                + "；".join(fact.statement for fact in world_model.canon_facts[:3])
            )
        return "\n".join(lines) if lines else "无"

    @staticmethod
    def _lorebook_context_text(lorebook_context: LorebookBundle | None) -> str:
        if lorebook_context is None or not lorebook_context.hits:
            return "无"
        hit_ids = {item.entry_id for item in lorebook_context.hits}
        matched_entries = [
            entry for entry in lorebook_context.entries if entry.entry_id in hit_ids
        ]
        if not matched_entries:
            return "无"
        return "\n".join(
            f"- {entry.title}: {entry.content}" for entry in matched_entries
        )

    async def generate(
        self,
        *,
        skeleton: ChapterSkeleton,
        style_profile: StyleProfile,
        style_samples: list[str],
        world_model: WorldModel | None = None,
        chapter_brief: ChapterBrief | None = None,
        lorebook_context: LorebookBundle | None = None,
    ) -> str:
        prompt = render_prompt(
            "generation/chapter_draft.txt",
            style_profile=style_profile.model_dump(mode="json"),
            style_samples=style_samples,
            chapter_skeleton=skeleton.model_dump(mode="json"),
            world_model=self._world_context_text(world_model),
            chapter_brief=chapter_brief.model_dump(mode="json") if chapter_brief else {},
            lorebook_context=self._lorebook_context_text(lorebook_context),
        )
        draft = await self.llm_service.complete_text(
            model=self.settings.models.draft_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=self.settings.models.chapter_max_tokens,
            operation="stage3_generate_draft",
        )
        return draft.text

    async def polish(
        self,
        *,
        draft_text: str,
        style_profile: StyleProfile,
        world_model: WorldModel | None = None,
        chapter_brief: ChapterBrief | None = None,
        lorebook_context: LorebookBundle | None = None,
    ) -> str:
        prompt = render_prompt(
            "generation/style_polish.txt",
            style_profile=style_profile.model_dump(mode="json"),
            world_model=self._world_context_text(world_model),
            chapter_brief=chapter_brief.model_dump(mode="json") if chapter_brief else {},
            lorebook_context=self._lorebook_context_text(lorebook_context),
            draft_text=draft_text,
        )
        polished = await self.llm_service.complete_text(
            model=self.settings.models.draft_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=self.settings.models.chapter_max_tokens,
            operation="stage3_polish_draft",
        )
        return polished.text

    async def revise(
        self,
        *,
        draft_text: str,
        style_profile: StyleProfile,
        issues: list[str],
        skeleton: ChapterSkeleton,
        world_model: WorldModel | None = None,
        chapter_brief: ChapterBrief | None = None,
        lorebook_context: LorebookBundle | None = None,
    ) -> str:
        prompt = (
            "请基于以下问题修订正文，保持剧情事实与章节骨架一致，不要输出说明。\n\n"
            f"[问题]\n{json.dumps(issues, ensure_ascii=False, indent=2)}\n\n"
            f"[风格画像]\n{style_profile.model_dump_json(indent=2)}\n\n"
            f"[世界约束]\n{self._world_context_text(world_model)}\n\n"
            f"[章节 brief]\n{chapter_brief.model_dump_json(indent=2) if chapter_brief else '无'}\n\n"
            f"[Lorebook 命中]\n{self._lorebook_context_text(lorebook_context)}\n\n"
            f"[章节骨架]\n{skeleton.model_dump_json(indent=2)}\n\n"
            f"[待修订正文]\n{draft_text}"
        )
        revised = await self.llm_service.complete_text(
            model=self.settings.models.draft_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=self.settings.models.chapter_max_tokens,
            operation="stage3_revise_draft",
        )
        return revised.text
