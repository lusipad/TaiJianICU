from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from config.settings import AppSettings
from webapp.app import create_app
from webapp.models import WebBenchmarkDetail, WebRunDetail, WebRunProgress, WebRunRequest, WebRunSummary


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

    def list_benchmarks(self):
        return [
            {
                "dataset_name": "demo",
                "case_name": "1_to_2",
                "target_chapter_number": 2,
                "prefix_chapter_count": 1,
                "winner": "system",
                "confidence": 0.9,
                "report_json_path": "benchmark_report.json",
                "report_markdown_path": "benchmark_report.md",
            }
        ]

    def get_benchmark(self, dataset_name: str, case_name: str):
        assert dataset_name == "demo"
        assert case_name == "1_to_2"
        return WebBenchmarkDetail(
            dataset_name="demo",
            case_name="1_to_2",
            target_chapter_number=2,
            prefix_chapter_count=1,
            winner="system",
            confidence=0.9,
            report_json_path="benchmark_report.json",
            report_markdown_path="benchmark_report.md",
            system_output_path="system.md",
            baseline_output_path="baseline.md",
            reference_path="reference.md",
            pairwise_reasoning=["更稳"],
            system_score=0.85,
            baseline_score=0.6,
            system_summary="更稳",
            baseline_summary="一般",
            system_strengths=["剧情推进稳"],
            baseline_strengths=["语言顺"],
            system_weaknesses=["爆点稍弱"],
            baseline_weaknesses=["偏离原著"],
            system_elapsed_seconds=12.3,
            baseline_elapsed_seconds=8.4,
            total_cost_usd=0.12,
            total_tokens=1234,
        )

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
    favicon = client.get("/static/favicon.svg")
    assert favicon.status_code == 200
    assert "image/svg+xml" in favicon.headers["content-type"]


def test_web_requires_basic_auth_when_password_configured() -> None:
    settings = AppSettings(TAIJIAN_WEB_PASSWORD="secret123")
    app = create_app(settings=settings, run_manager=FakeRunManager())
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    index_response = client.get("/")
    assert index_response.status_code == 401
    assert "Basic" in index_response.headers["www-authenticate"]

    authed_response = client.get("/", auth=("admin", "secret123"))
    assert authed_response.status_code == 200
    assert "TaiJianKiller Studio" in authed_response.text


def test_api_requires_basic_auth_when_password_configured() -> None:
    settings = AppSettings(TAIJIAN_WEB_PASSWORD="secret123")
    app = create_app(settings=settings, run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/runs")
    assert response.status_code == 401

    authed = client.get("/api/runs", auth=("admin", "secret123"))
    assert authed.status_code == 200
    assert authed.json()[0]["id"] == "run-1"


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


def test_list_benchmarks_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/benchmarks")

    assert response.status_code == 200
    assert response.json()[0]["dataset_name"] == "demo"


def test_get_benchmark_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/benchmarks/demo/1_to_2")

    assert response.status_code == 200
    assert response.json()["system_summary"] == "更稳"
