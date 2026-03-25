from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class SceneNode(BaseModel):
    scene_type: str
    participants: list[str] = Field(default_factory=list)
    scene_purpose: str
    estimated_word_count: int = 800

    @field_validator("estimated_word_count")
    @classmethod
    def validate_word_count(cls, value: int) -> int:
        return max(200, value)


class AgentProposal(BaseModel):
    character_name: str = ""
    goal: str
    action_proposal: str
    reasoning: str
    risks: list[str] = Field(default_factory=list)


class DebateCritique(BaseModel):
    character_name: str = ""
    stance: str
    critique: str
    supports: list[str] = Field(default_factory=list)
    opposes: list[str] = Field(default_factory=list)


class ArbitrationDecision(BaseModel):
    chapter_theme: str
    winning_plan: str
    rejected_points: list[str] = Field(default_factory=list)
    must_include_beats: list[str] = Field(default_factory=list)
    threads_to_advance: list[str] = Field(default_factory=list)


class AgentConsensusLog(BaseModel):
    round_name: str
    speaker: str
    content: str


class ChapterSkeleton(BaseModel):
    chapter_number: int
    chapter_theme: str
    scenes: list[SceneNode]
    threads_to_advance: list[str] = Field(default_factory=list)
    threads_to_close: list[str] = Field(default_factory=list)
    agent_consensus_log: list[AgentConsensusLog] = Field(default_factory=list)
    was_human_revised: bool = False

    @field_validator("scenes")
    @classmethod
    def validate_scenes(cls, value: list[SceneNode]) -> list[SceneNode]:
        if not value:
            raise ValueError("章节骨架至少需要一个场景")
        return value
