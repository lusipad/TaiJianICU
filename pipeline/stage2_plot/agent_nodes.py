from __future__ import annotations

import json
from typing import Iterable

from pydantic import BaseModel, Field

from config.settings import AppSettings, render_prompt
from core.models.chapter_brief import ChapterBrief
from core.models.lorebook import LorebookBundle
from core.llm.litellm_client import LiteLLMService
from core.models.skeleton import AgentProposal, ArbitrationDecision, DebateCritique
from core.models.story_state import CharacterCard, StoryThread, StoryWorldState
from core.models.world_model import WorldModel
from core.storage.lightrag_store import LightRAGStore


class DebateCritiqueBatch(BaseModel):
    critiques: list[DebateCritique] = Field(default_factory=list)


class AgentNodeService:
    def __init__(
        self,
        settings: AppSettings,
        llm_service: LiteLLMService,
        rag_store: LightRAGStore,
    ):
        self.settings = settings
        self.llm_service = llm_service
        self.rag_store = rag_store

    def _focus_threads_text(self, threads: Iterable[StoryThread]) -> str:
        items = [f"{thread.id}: {thread.description}" for thread in threads]
        return "\n".join(items) if items else "无"

    @staticmethod
    def _world_context_text(world_model: WorldModel | None) -> str:
        if world_model is None:
            return "无"
        lines: list[str] = []
        if world_model.summary:
            lines.append(f"摘要：{world_model.summary}")
        if world_model.world_tensions:
            lines.append(f"世界张力：{'；'.join(world_model.world_tensions[:3])}")
        if world_model.open_mysteries:
            lines.append(f"未解谜团：{'；'.join(world_model.open_mysteries[:3])}")
        if world_model.canon_facts:
            lines.append(
                "硬设定："
                + "；".join(fact.statement for fact in world_model.canon_facts[:3])
            )
        return "\n".join(lines) if lines else "无"

    @staticmethod
    def _chapter_brief_text(chapter_brief: ChapterBrief | None) -> str:
        if chapter_brief is None:
            return "无"
        lines = [f"章节目标：{chapter_brief.chapter_goal}"]
        if chapter_brief.must_happen:
            lines.append(f"必须发生：{'；'.join(chapter_brief.must_happen)}")
        if chapter_brief.must_not_break:
            lines.append(f"禁止破坏：{'；'.join(chapter_brief.must_not_break[:3])}")
        if chapter_brief.constraints:
            lines.append(
                "附加约束："
                + "；".join(constraint.content for constraint in chapter_brief.constraints[:3])
            )
        return "\n".join(lines)

    @staticmethod
    def _lorebook_context_text(lorebook_context: LorebookBundle | None) -> str:
        if lorebook_context is None or not lorebook_context.hits:
            return "无"
        hit_scores = {item.entry_id: item.score for item in lorebook_context.hits}
        selected = [
            entry for entry in lorebook_context.entries if entry.entry_id in hit_scores
        ]
        selected.sort(key=lambda entry: hit_scores[entry.entry_id], reverse=True)
        lines = []
        for entry in selected:
            prefix = "硬约束" if entry.hard_constraint else "参考"
            lines.append(f"[{prefix}] {entry.title}: {entry.content}")
        return "\n".join(lines) if lines else "无"

    async def load_context(
        self,
        *,
        session_name: str,
        chapter_goal: str,
        story_state: StoryWorldState,
        world_model: WorldModel | None,
        chapter_brief: ChapterBrief | None,
        lorebook_context: LorebookBundle | None,
        focus_threads: list[StoryThread],
    ) -> str:
        query = (
            f"围绕以下章节目标提取关键记忆：{chapter_goal}\n"
            f"主要角色：{', '.join(card.name for card in story_state.main_characters[:4])}\n"
            f"需要推进的伏笔：{self._focus_threads_text(focus_threads)}\n"
            f"章节 brief：{self._chapter_brief_text(chapter_brief)}\n"
            f"世界约束：{self._world_context_text(world_model)}\n"
            f"Lorebook 命中：{self._lorebook_context_text(lorebook_context)}"
        )
        return await self.rag_store.query_context(
            session_name,
            query,
            response_type="Bullet Points",
        )

    async def build_proposals(
        self,
        *,
        chapter_goal: str,
        story_state: StoryWorldState,
        world_model: WorldModel | None,
        chapter_brief: ChapterBrief | None,
        lorebook_context: LorebookBundle | None,
        recalled_context: str,
        focus_threads: list[StoryThread],
    ) -> list[AgentProposal]:
        characters = story_state.main_characters[:3] or [
            CharacterCard(
                name="主角",
                role="默认主视角",
                personality_traits=["谨慎", "求胜"],
                core_goals=["推进主线冲突"],
                speech_style="简练",
                last_known_state="故事正在推进",
            )
        ]
        proposals: list[AgentProposal] = []
        for card in characters:
            prompt = render_prompt(
                "agents/character_agent.txt",
                character_name=card.name,
                role=card.role,
                personality_traits=card.personality_traits,
                core_goals=card.core_goals,
                speech_style=card.speech_style,
                last_known_state=card.last_known_state,
                chapter_goal=chapter_goal,
                chapter_brief=self._chapter_brief_text(chapter_brief),
                world_context=self._world_context_text(world_model),
                lorebook_context=self._lorebook_context_text(lorebook_context),
                recalled_context=recalled_context,
                focus_threads=self._focus_threads_text(focus_threads),
            )
            proposal = await self.llm_service.complete_structured(
                model=self.settings.models.plot_model,
                messages=[{"role": "user", "content": prompt}],
                response_model=AgentProposal,
                temperature=0.5,
                operation="stage2_character_proposal",
            )
            proposal.character_name = card.name
            proposals.append(proposal)
        return proposals

    async def build_critiques(
        self,
        *,
        chapter_goal: str,
        story_state: StoryWorldState,
        world_model: WorldModel | None,
        chapter_brief: ChapterBrief | None,
        lorebook_context: LorebookBundle | None,
        proposals: list[AgentProposal],
        recalled_context: str,
    ) -> list[DebateCritique]:
        prompt = (
            "你是小说策划会议记录员。请阅读下列角色提案，输出每个角色的立场、支持点和反对点。"
            "要求聚焦人物动机冲突、伏笔推进与节奏风险。\n\n"
            f"[章节目标]\n{chapter_goal}\n\n"
            f"[故事状态]\n{story_state.summary}\n\n"
            f"[章节 brief]\n{self._chapter_brief_text(chapter_brief)}\n\n"
            f"[世界约束]\n{self._world_context_text(world_model)}\n\n"
            f"[Lorebook 命中]\n{self._lorebook_context_text(lorebook_context)}\n\n"
            f"[检索记忆]\n{recalled_context}\n\n"
            f"[角色提案]\n{json.dumps([item.model_dump(mode='json') for item in proposals], ensure_ascii=False, indent=2)}"
        )
        batch = await self.llm_service.complete_structured(
            model=self.settings.models.plot_model,
            messages=[{"role": "user", "content": prompt}],
            response_model=DebateCritiqueBatch,
            temperature=0.3,
            operation="stage2_debate_critique",
        )
        return batch.critiques

    async def arbitrate(
        self,
        *,
        chapter_number: int,
        chapter_goal: str,
        story_state: StoryWorldState,
        world_model: WorldModel | None,
        chapter_brief: ChapterBrief | None,
        lorebook_context: LorebookBundle | None,
        focus_threads: list[StoryThread],
        proposals: list[AgentProposal],
        critiques: list[DebateCritique],
    ) -> ArbitrationDecision:
        prompt = render_prompt(
            "agents/author_agent.txt",
            chapter_number=chapter_number,
            chapter_goal=chapter_goal,
            world_summary=story_state.summary,
            active_conflicts=story_state.active_conflicts,
            world_context=self._world_context_text(world_model),
            chapter_brief=self._chapter_brief_text(chapter_brief),
            lorebook_context=self._lorebook_context_text(lorebook_context),
            focus_threads=self._focus_threads_text(focus_threads),
            proposal_bundle=[item.model_dump(mode="json") for item in proposals],
            critique_bundle=[item.model_dump(mode="json") for item in critiques],
        )
        return await self.llm_service.complete_structured(
            model=self.settings.models.plot_model,
            messages=[{"role": "user", "content": prompt}],
            response_model=ArbitrationDecision,
            temperature=0.3,
            operation="stage2_author_arbitrate",
        )
