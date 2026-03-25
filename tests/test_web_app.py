from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from config.settings import AppSettings
from webapp.app import create_app
from webapp.models import WebRunDetail, WebRunProgress, WebRunRequest, WebRunSummary


class FakeRunManager:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.detail = WebRunDetail(
            id="run-1",
            status="completed",
            created_at=now,
            updated_at=now,
            session_name="demo-session",
            input_filename="demo.txt",
            request=WebRunRequest(chapters=1, start_chapter=1),
            progress=WebRunProgress(total_steps=5, completed_steps=5, message="运行完成"),
            log_messages=["阶段1：索引与风格分析", "运行完成"],
            input_path="demo.txt",
            output_paths=["chapter_1.md"],
            latest_output_preview="示例正文",
        )
        self.start_calls = 0
        self.last_request = None

    def list_runs(self):
        return [WebRunSummary.model_validate(self.detail.model_dump(mode="json"))]

    def get_run(self, run_id: str):
        assert run_id == "run-1"
        return self.detail

    def save_uploaded_text(self, filename: str, content: bytes):
        return Path("demo.txt"), "demo"

    def start_run(self, *, input_path: Path, input_filename: str, request: WebRunRequest):
        self.start_calls += 1
        self.last_request = request
        return WebRunSummary.model_validate(self.detail.model_dump(mode="json"))


def test_web_health_and_index() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 200
    assert "TaiJianKiller Studio" in response.text
    assert "世界模型" in response.text


def test_create_run_rejects_non_txt_upload() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        files={"file": ("demo.md", b"# nope", "text/markdown")},
        data={"chapters": "1", "start_chapter": "1"},
    )

    assert response.status_code == 422
    assert "txt" in response.json()["detail"]


def test_create_run_accepts_txt_upload() -> None:
    manager = FakeRunManager()
    app = create_app(settings=AppSettings(), run_manager=manager)
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        files={"file": ("demo.txt", "第一章 测试".encode("utf-8"), "text/plain")},
        data={
            "chapters": "1",
            "start_chapter": "1",
            "planning_mode": "expansive",
            "new_character_budget": "2",
            "new_location_budget": "1",
            "new_faction_budget": "1",
            "skeleton_candidates": "2",
            "draft_candidates": "3",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == "run-1"
    assert response.json()["progress"]["percent"] == 100.0
    assert response.json()["progress"]["completed_label"] == "5/5"
    assert manager.start_calls == 1
    assert manager.last_request.planning_mode == "expansive"
    assert manager.last_request.new_character_budget == 2
    assert manager.last_request.new_location_budget == 1
    assert manager.last_request.new_faction_budget == 1
    assert manager.last_request.skeleton_candidates == 2
    assert manager.last_request.draft_candidates == 3
