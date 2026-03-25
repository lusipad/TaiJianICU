from __future__ import annotations

from core.models.arc_outline import ArcBeat, ArcOutline, PlannedIntroduction
from core.models.chapter_brief import ExpansionBudget
from core.models.world_model import WorldModel


class ArcPlanner:
    def plan(
        self,
        *,
        world_model: WorldModel,
        start_chapter: int,
        arc_length: int,
        expansion_budget: ExpansionBudget,
    ) -> ArcOutline:
        end_chapter = start_chapter + arc_length - 1
        theme = world_model.world_tensions[0] if world_model.world_tensions else (world_model.summary or "主线推进")
        goal = world_model.open_mysteries[0] if world_model.open_mysteries else theme
        required_setups = [
            ArcBeat(
                label=f"setup_{index:02d}",
                description=item,
                target_chapter=min(end_chapter, start_chapter + index - 1),
                mandatory=True,
            )
            for index, item in enumerate(world_model.world_tensions[:2] or [theme], start=1)
        ]
        required_payoffs = [
            ArcBeat(
                label=f"payoff_{index:02d}",
                description=item,
                target_chapter=end_chapter,
                mandatory=(index == 1),
            )
            for index, item in enumerate(world_model.open_mysteries[:2] or [goal], start=1)
        ]

        new_character_plan: list[PlannedIntroduction] = []
        if expansion_budget.new_character_budget:
            new_character_plan.append(
                PlannedIntroduction(
                    plan_type="character",
                    name="new_character_slot",
                    purpose="为当前 arc 引入新的冲突推动者或观察者",
                    entry_condition="在前半段制造新的信息或压力来源",
                    mandatory=False,
                )
            )

        new_location_plan: list[PlannedIntroduction] = []
        if expansion_budget.new_location_budget:
            new_location_plan.append(
                PlannedIntroduction(
                    plan_type="location",
                    name="new_location_slot",
                    purpose="扩大世界边界，提供新的舞台与资源结构",
                    entry_condition="在中段或末段承接已有冲突升级",
                    mandatory=False,
                )
            )

        new_faction_plan: list[PlannedIntroduction] = []
        if expansion_budget.new_faction_budget:
            new_faction_plan.append(
                PlannedIntroduction(
                    plan_type="faction",
                    name="new_faction_slot",
                    purpose="让现有冲突外部化或升级化",
                    entry_condition="当旧冲突即将显性化时介入",
                    mandatory=False,
                )
            )

        twist_plan = []
        if expansion_budget.twist_budget:
            twist_plan.append(
                ArcBeat(
                    label="twist_01",
                    description="在 arc 中后段引入一次立场反转或信息反转",
                    target_chapter=min(end_chapter, start_chapter + max(1, arc_length - 2)),
                    mandatory=False,
                )
            )

        return ArcOutline(
            arc_id=f"arc_{start_chapter:04d}_{end_chapter:04d}",
            arc_theme=theme,
            arc_goal=goal,
            phase="setup",
            chapters_span=[start_chapter, end_chapter],
            required_payoffs=required_payoffs,
            required_setups=required_setups,
            new_character_plan=new_character_plan,
            new_location_plan=new_location_plan,
            new_faction_plan=new_faction_plan,
            twist_plan=twist_plan,
            exit_condition=f"完成 {goal} 的阶段推进，并为下一卷留下新的压力源。",
            summary=f"第{start_chapter}章到第{end_chapter}章围绕“{theme}”推进。",
        )
