from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from core.models.skeleton import ChapterSkeleton
from core.storage.session_store import SessionStore


class InterventionConfig(BaseModel):
    must_happen: list[str] = Field(default_factory=list)
    focus_thread_ids: list[str] = Field(default_factory=list)
    notes: str = ""


class InterventionManager:
    def __init__(self, session_store: SessionStore):
        self.session_store = session_store

    def load_or_create(self, session_name: str, chapter_number: int) -> InterventionConfig:
        path = self.session_store.chapter_config_path(session_name, chapter_number)
        if path.exists():
            return InterventionConfig.model_validate_json(path.read_text(encoding="utf-8"))
        config = InterventionConfig()
        self.session_store.save_model(path, config)
        return config

    def skeleton_override_path(self, session_name: str, chapter_number: int) -> Path:
        return self.session_store.session_dir(session_name) / f"chapter_{chapter_number}_skeleton.override.json"

    def draft_override_path(self, session_name: str, chapter_number: int) -> Path:
        return self.session_store.session_dir(session_name) / f"chapter_{chapter_number}_draft.override.md"

    def apply_skeleton_override(
        self,
        session_name: str,
        chapter_number: int,
        skeleton: ChapterSkeleton,
    ) -> ChapterSkeleton:
        override_path = self.skeleton_override_path(session_name, chapter_number)
        if not override_path.exists():
            return skeleton
        return ChapterSkeleton.model_validate_json(override_path.read_text(encoding="utf-8"))

    def apply_draft_override(
        self,
        session_name: str,
        chapter_number: int,
        draft_text: str,
    ) -> str:
        override_path = self.draft_override_path(session_name, chapter_number)
        if not override_path.exists():
            return draft_text
        return override_path.read_text(encoding="utf-8")
