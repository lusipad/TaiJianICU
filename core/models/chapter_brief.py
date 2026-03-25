from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Mode = Literal["strict", "balanced", "expansive"]
ExpansionMode = Literal["hold", "light", "medium", "strong"]


class ExpansionBudget(BaseModel):
    mode: Mode = "balanced"
    expansion_mode: ExpansionMode = "light"
    new_character_budget: int = 0
    new_location_budget: int = 0
    new_faction_budget: int = 0
    twist_budget: int = 0
    reveal_budget: int = 0
    replanning_required: bool = False


class AllowedExpansion(BaseModel):
    new_character: bool = False
    new_location: bool = False
    new_faction: bool = False
    new_mystery: bool = False


class ChapterConstraint(BaseModel):
    label: str
    content: str
    priority: Literal["hard", "soft"] = "hard"


class ChapterBrief(BaseModel):
    chapter_number: int
    chapter_goal: str
    chapter_note: str = ""
    tone_target: str = ""
    must_happen: list[str] = Field(default_factory=list)
    may_introduce: list[str] = Field(default_factory=list)
    must_not_break: list[str] = Field(default_factory=list)
    focus_threads: list[str] = Field(default_factory=list)
    constraints: list[ChapterConstraint] = Field(default_factory=list)
    allowed_expansion: AllowedExpansion = Field(default_factory=AllowedExpansion)
    expansion_budget: ExpansionBudget = Field(default_factory=ExpansionBudget)
