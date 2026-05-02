from __future__ import annotations

import json
import re

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

    @staticmethod
    def strip_output_shell(text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:\w+)?\s*", "", cleaned)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = re.sub(
            r"^以下(?:为|是).{0,20}(?:正文|续写|草稿|润色稿|修订稿)[：:]\s*",
            "",
            cleaned,
        )
        cleaned = re.sub(r"^(?:-{3,}|={3,})\s*", "", cleaned)
        return cleaned.strip()

    @staticmethod
    def sanitize_generation_payload(value):
        if isinstance(value, dict):
            return {
                key: ChapterGenerator.sanitize_generation_payload(item)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [ChapterGenerator.sanitize_generation_payload(item) for item in value]
        if not isinstance(value, str):
            return value
        cleaned = value
        replacements = {
            "宿命之问": "疑问",
            "宿命": "命数",
            "象征意义": "影子里的话头",
            "象征": "影子",
            "主题升华": "场面收束",
            "主题": "话头",
            "结构性风险": "场面旁逸",
            "结构风险": "场面旁逸",
            "现实苦难": "眼前苦楚",
            "活生生的注脚": "眼前一事",
            "无声在场": "远远看见",
        }
        for source, target in replacements.items():
            cleaned = cleaned.replace(source, target)
        return cleaned

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
            chapter_skeleton=self.sanitize_generation_payload(
                skeleton.model_dump(mode="json")
            ),
            world_model=self._world_context_text(world_model),
            chapter_brief=(
                self.sanitize_generation_payload(chapter_brief.model_dump(mode="json"))
                if chapter_brief
                else {}
            ),
            lorebook_context=self._lorebook_context_text(lorebook_context),
        )
        draft = await self.llm_service.complete_text(
            model=self.settings.models.draft_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            max_tokens=self.settings.models.chapter_max_tokens,
            operation="stage3_generate_draft",
        )
        return self.strip_output_shell(draft.text)

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
            chapter_brief=(
                self.sanitize_generation_payload(chapter_brief.model_dump(mode="json"))
                if chapter_brief
                else {}
            ),
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
        return self.strip_output_shell(polished.text)

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
            "[章节 brief]\n"
            f"{json.dumps(self.sanitize_generation_payload(chapter_brief.model_dump(mode='json')), ensure_ascii=False, indent=2) if chapter_brief else '无'}\n\n"
            f"[Lorebook 命中]\n{self._lorebook_context_text(lorebook_context)}\n\n"
            "[章节骨架]\n"
            f"{json.dumps(self.sanitize_generation_payload(skeleton.model_dump(mode='json')), ensure_ascii=False, indent=2)}\n\n"
            f"[待修订正文]\n{draft_text}"
        )
        revised = await self.llm_service.complete_text(
            model=self.settings.models.draft_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.5,
            max_tokens=self.settings.models.chapter_max_tokens,
            operation="stage3_revise_draft",
        )
        return self.strip_output_shell(revised.text)
