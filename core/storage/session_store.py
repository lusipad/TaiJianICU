from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from core.models.story_state import StoryThread


class SessionStore:
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, payload: Any) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def _read_json(self, path: Path, default: Any) -> Any:
        if not path.exists():
            return default
        return json.loads(path.read_text(encoding="utf-8"))

    def save_model(self, path: Path, model: BaseModel) -> Path:
        return self._write_json(path, model.model_dump(mode="json"))

    def load_model(self, path: Path, model_cls: type[BaseModel]) -> BaseModel | None:
        if not path.exists():
            return None
        return model_cls.model_validate_json(path.read_text(encoding="utf-8"))

    def session_dir(self, session_name: str) -> Path:
        path = self.base_dir / session_name
        path.mkdir(parents=True, exist_ok=True)
        return path

    def unresolved_threads_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "unresolved_threads.json"

    def load_unresolved_threads(self, session_name: str) -> list[StoryThread]:
        payload = self._read_json(self.unresolved_threads_path(session_name), {"threads": []})
        return [StoryThread.model_validate(item) for item in payload.get("threads", [])]

    def save_unresolved_threads(
        self,
        session_name: str,
        threads: list[StoryThread],
    ) -> Path:
        return self._write_json(
            self.unresolved_threads_path(session_name),
            {"threads": [thread.model_dump(mode="json") for thread in threads]},
        )

    def chapter_config_path(self, session_name: str, chapter_number: int) -> Path:
        return self.session_dir(session_name) / f"chapter_{chapter_number}_config.json"

    def chapter_skeleton_path(self, session_name: str, chapter_number: int) -> Path:
        return self.session_dir(session_name) / f"chapter_{chapter_number}_skeleton.json"

    def chapter_skeleton_candidate_path(
        self,
        session_name: str,
        chapter_number: int,
        candidate_number: int,
    ) -> Path:
        return (
            self.session_dir(session_name)
            / "candidates"
            / f"chapter_{chapter_number}_skeleton_candidate_{candidate_number}.json"
        )

    def chapter_draft_path(self, session_name: str, chapter_number: int) -> Path:
        return self.session_dir(session_name) / f"chapter_{chapter_number}_draft.md"

    def chapter_revival_candidate_path(self, session_name: str, chapter_number: int) -> Path:
        return self.session_dir(session_name) / f"chapter_{chapter_number}_revival_candidate.md"

    def chapter_draft_candidate_path(
        self,
        session_name: str,
        chapter_number: int,
        candidate_number: int,
    ) -> Path:
        return (
            self.session_dir(session_name)
            / "candidates"
            / f"chapter_{chapter_number}_draft_candidate_{candidate_number}.md"
        )

    def stage1_snapshot_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "stage1_snapshot.json"

    def world_model_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "world_model.json"

    def arc_outline_path(self, session_name: str, arc_id: str) -> Path:
        return self.session_dir(session_name) / "arcs" / f"{arc_id}.json"

    def lorebook_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "lorebook.json"

    def selected_references_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "selected_references.json"

    def work_skill_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "work_skill.json"

    def revival_workspace_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "revival_workspace.json"

    def arc_options_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "arc_options.json"

    def selected_arc_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "selected_arc.json"

    def revival_diagnosis_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "revival_diagnosis.json"

    def blind_challenge_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "blind_challenge.json"

    def blind_judge_report_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "blind_judge_report.json"

    def chapter_brief_path(self, session_name: str, chapter_number: int) -> Path:
        return self.session_dir(session_name) / f"chapter_{chapter_number}_brief.json"

    def chapter_evaluation_path(self, session_name: str, chapter_number: int) -> Path:
        return self.session_dir(session_name) / f"chapter_{chapter_number}_evaluation.json"

    def run_manifest_path(self, session_name: str) -> Path:
        return self.session_dir(session_name) / "run_manifest.json"

    def save_text(self, path: Path, content: str) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path
