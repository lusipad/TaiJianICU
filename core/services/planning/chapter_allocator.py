from __future__ import annotations

from core.models.arc_outline import ArcOutline
from core.models.chapter_brief import (
    AllowedExpansion,
    ChapterBrief,
    ChapterConstraint,
    ExpansionBudget,
)
from core.models.world_model import WorldModel


class ChapterAllocator:
    def allocate(
        self,
        *,
        world_model: WorldModel,
        arc_outline: ArcOutline,
        chapter_number: int,
        expansion_budget: ExpansionBudget,
    ) -> ChapterBrief:
        start, end = arc_outline.chapters_span
        midpoint = (start + end) // 2
        must_happen = self._build_must_happen(arc_outline, chapter_number, midpoint, end)
        may_introduce = []
        if expansion_budget.new_character_budget and chapter_number >= midpoint:
            may_introduce.append("允许引入一个与主线因果相连的新人物")
        if expansion_budget.new_location_budget and chapter_number >= midpoint:
            may_introduce.append("允许切入一个承接旧冲突的新地图")
        if expansion_budget.new_faction_budget and chapter_number >= midpoint:
            may_introduce.append("允许展示一个尚未正式登场的新势力")

        focus_threads = [thread.id for thread in world_model.active_threads[:2]]
        return ChapterBrief(
            chapter_number=chapter_number,
            chapter_goal=self._build_chapter_goal(arc_outline, chapter_number, midpoint, end),
            chapter_note=f"当前 arc 主题：{arc_outline.arc_theme}",
            tone_target="稳住连续性，但允许结构性扩张",
            must_happen=must_happen,
            may_introduce=may_introduce,
            must_not_break=[fact.statement for fact in world_model.canon_facts[:3]],
            focus_threads=focus_threads,
            constraints=[
                ChapterConstraint(
                    label="arc_alignment",
                    content=f"本章必须服务于 arc 目标：{arc_outline.arc_goal}",
                    priority="hard",
                )
            ],
            allowed_expansion=AllowedExpansion(
                new_character=bool(expansion_budget.new_character_budget and chapter_number >= midpoint),
                new_location=bool(expansion_budget.new_location_budget and chapter_number >= midpoint),
                new_faction=bool(expansion_budget.new_faction_budget and chapter_number >= midpoint),
                new_mystery=bool(expansion_budget.reveal_budget),
            ),
            expansion_budget=expansion_budget,
        )

    @staticmethod
    def _build_must_happen(
        arc_outline: ArcOutline,
        chapter_number: int,
        midpoint: int,
        end: int,
    ) -> list[str]:
        if chapter_number == arc_outline.chapters_span[0]:
            return [item.description for item in arc_outline.required_setups[:1]]
        if chapter_number >= end - 1:
            return [item.description for item in arc_outline.required_payoffs[:1]]
        if chapter_number >= midpoint and arc_outline.twist_plan:
            return [arc_outline.twist_plan[0].description]
        return [item.description for item in arc_outline.required_setups[:1]]

    @staticmethod
    def _build_chapter_goal(
        arc_outline: ArcOutline,
        chapter_number: int,
        midpoint: int,
        end: int,
    ) -> str:
        if chapter_number == arc_outline.chapters_span[0]:
            return f"为当前 arc 建立舞台与冲突：{arc_outline.arc_theme}"
        if chapter_number >= end - 1:
            return f"把当前 arc 推向 payoff：{arc_outline.arc_goal}"
        if chapter_number >= midpoint:
            return f"放大中段压力并准备转折：{arc_outline.arc_goal}"
        return f"继续加压并巩固当前 arc：{arc_outline.arc_theme}"
