from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from core.models.story_state import StoryThread


ImportanceLevel = Literal["low", "medium", "high", "critical"]
ThreatLevel = Literal["low", "medium", "high"]
ConstraintLevel = Literal["hard", "soft"]
ExpansionType = Literal["character", "location", "faction", "mystery", "power"]


class CanonFact(BaseModel):
    id: str
    category: str
    statement: str
    source_chapter: int = 0
    level: ConstraintLevel = "hard"


class CharacterArc(BaseModel):
    character_name: str
    role: str = ""
    current_state: str = ""
    public_persona: str = ""
    core_wants: list[str] = Field(default_factory=list)
    hidden_pressure: list[str] = Field(default_factory=list)
    recent_change: str = ""
    arc_direction: str = ""
    taboos: list[str] = Field(default_factory=list)
    relationship_notes: list[str] = Field(default_factory=list)


class FactionState(BaseModel):
    name: str
    public_goal: str = ""
    hidden_goal: str = ""
    current_resources: list[str] = Field(default_factory=list)
    relation_map: list[str] = Field(default_factory=list)
    recent_move: str = ""
    threat_level: ThreatLevel = "medium"


class LocationState(BaseModel):
    name: str
    location_type: str = ""
    importance: ImportanceLevel = "medium"
    connected_locations: list[str] = Field(default_factory=list)
    current_risk: list[str] = Field(default_factory=list)
    story_function: str = ""
    current_status: str = ""


class ExpansionSlot(BaseModel):
    slot_id: str
    slot_type: ExpansionType
    description: str
    trigger_hint: str = ""
    priority: ImportanceLevel = "medium"


class WorldModel(BaseModel):
    title: str | None = None
    summary: str = ""
    canon_facts: list[CanonFact] = Field(default_factory=list)
    power_system_rules: list[str] = Field(default_factory=list)
    main_characters: list[CharacterArc] = Field(default_factory=list)
    active_factions: list[FactionState] = Field(default_factory=list)
    known_locations: list[LocationState] = Field(default_factory=list)
    world_tensions: list[str] = Field(default_factory=list)
    open_mysteries: list[str] = Field(default_factory=list)
    expansion_slots: list[ExpansionSlot] = Field(default_factory=list)
    active_threads: list[StoryThread] = Field(default_factory=list)
    last_refreshed_chapter: int = 0
