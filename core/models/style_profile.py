from __future__ import annotations

from pydantic import BaseModel, Field

from core.models.story_state import StoryWorldState


class StyleProfile(BaseModel):
    narrative_person: str = "第三人称"
    pacing: str = "中速推进"
    tone_keywords: list[str] = Field(default_factory=list)
    sentence_rhythm: str = ""
    dialogue_style: str = ""
    signature_devices: list[str] = Field(default_factory=list)
    taboo_patterns: list[str] = Field(default_factory=list)
    summary: str = ""


class ExtractionSnapshot(BaseModel):
    style_profile: StyleProfile
    story_state: StoryWorldState
