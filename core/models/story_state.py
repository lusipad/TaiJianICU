from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class CharacterCard(BaseModel):
    name: str
    role: str = ""
    personality_traits: list[str] = Field(default_factory=list)
    core_goals: list[str] = Field(default_factory=list)
    speech_style: str = ""
    last_known_state: str = ""


class StoryThread(BaseModel):
    id: str
    description: str
    introduced_at: int = 0
    last_advanced: int = 0
    status: Literal["open", "advanced", "closed"] = "open"


class StoryWorldState(BaseModel):
    title: str | None = None
    summary: str = ""
    world_rules: list[str] = Field(default_factory=list)
    main_characters: list[CharacterCard] = Field(default_factory=list)
    major_relationships: list[str] = Field(default_factory=list)
    active_conflicts: list[str] = Field(default_factory=list)
    unresolved_threads: list[StoryThread] = Field(default_factory=list)
