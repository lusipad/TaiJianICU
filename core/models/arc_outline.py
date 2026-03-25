from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ArcPhase = Literal["setup", "escalation", "collision", "payoff", "cooldown"]
PlanType = Literal["character", "location", "faction", "mystery", "twist"]


class PlannedIntroduction(BaseModel):
    plan_type: PlanType
    name: str = ""
    purpose: str
    entry_condition: str = ""
    mandatory: bool = False


class ArcBeat(BaseModel):
    label: str
    description: str
    target_chapter: int | None = None
    mandatory: bool = True


class ArcOutline(BaseModel):
    arc_id: str
    arc_theme: str
    arc_goal: str
    phase: ArcPhase = "setup"
    chapters_span: list[int] = Field(default_factory=list, min_length=2, max_length=2)
    required_payoffs: list[ArcBeat] = Field(default_factory=list)
    required_setups: list[ArcBeat] = Field(default_factory=list)
    new_character_plan: list[PlannedIntroduction] = Field(default_factory=list)
    new_location_plan: list[PlannedIntroduction] = Field(default_factory=list)
    new_faction_plan: list[PlannedIntroduction] = Field(default_factory=list)
    twist_plan: list[ArcBeat] = Field(default_factory=list)
    exit_condition: str = ""
    summary: str = ""
