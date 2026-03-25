from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


LoreScope = Literal["global", "arc", "chapter"]
LoreEntryType = Literal["canon", "faction", "location", "character", "mystery", "tone"]


class LorebookEntry(BaseModel):
    entry_id: str
    title: str
    entry_type: LoreEntryType = "canon"
    scope: LoreScope = "global"
    content: str
    keywords: list[str] = Field(default_factory=list)
    semantic_queries: list[str] = Field(default_factory=list)
    priority: int = 50
    hard_constraint: bool = False
    budget_hint: int = 400
    enabled: bool = True


class LorebookHit(BaseModel):
    entry_id: str
    reason: str
    score: float = 0.0


class LorebookBundle(BaseModel):
    entries: list[LorebookEntry] = Field(default_factory=list)
    hits: list[LorebookHit] = Field(default_factory=list)
