from __future__ import annotations

from pydantic import BaseModel, Field


class MemorySnapshot(BaseModel):
    recent_excerpt: str = ""
    middle_summary: str = ""
    long_term_summary: str = ""
    lore_candidates: list[str] = Field(default_factory=list)
