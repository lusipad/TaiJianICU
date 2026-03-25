from __future__ import annotations

from pydantic import BaseModel, Field


class EvaluationScore(BaseModel):
    continuity_score: float = 0.0
    character_score: float = 0.0
    world_consistency_score: float = 0.0
    novelty_score: float = 0.0
    arc_progress_score: float = 0.0


class EvaluationFlag(BaseModel):
    code: str
    message: str
    severity: str = "warning"


class ChapterEvaluation(BaseModel):
    chapter_number: int
    score: EvaluationScore = Field(default_factory=EvaluationScore)
    flags: list[EvaluationFlag] = Field(default_factory=list)
    summary: str = ""
    should_retry: bool = False
