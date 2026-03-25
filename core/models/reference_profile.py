from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


ReferenceType = Literal["theme", "structure", "world", "character"]
ReferenceMode = Literal["off", "assist", "strong"]
ReferenceScope = Literal["arc", "chapter"]


class ReferenceTrait(BaseModel):
    label: str
    description: str


class ReferenceProfile(BaseModel):
    name: str
    reference_type: ReferenceType
    mode: ReferenceMode = "assist"
    abstract_traits: list[ReferenceTrait] = Field(default_factory=list)
    allowed_influences: list[str] = Field(default_factory=list)
    forbidden_copying: list[str] = Field(default_factory=list)
    use_scope: ReferenceScope = "arc"
    notes: str = ""
