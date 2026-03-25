from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from config.settings import AppSettings
from webapp.manager import WebRunManager
from webapp.models import WebRunDetail, WebRunProgress, WebRunRequest


def build_settings(tmp_path: Path) -> AppSettings:
    settings = AppSettings(
        work_dir=tmp_path,
        input_dir=tmp_path / "input",
        output_dir=tmp_path / "output",
        sessions_dir=tmp_path / "sessions",
        lightrag_dir=tmp_path / "lightrag",
        benchmarks_dir=tmp_path / "benchmarks",
        web_dir=tmp_path / "web",
        web_uploads_dir=tmp_path / "web" / "uploads",
        web_runs_dir=tmp_path / "web" / "runs",
    )
    settings.ensure_directories()
    return settings


def test_web_run_manager_loads_persisted_runs(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    now = datetime.now(timezone.utc)
    run = WebRunDetail(
        id="persisted-run",
        status="completed",
        created_at=now,
        updated_at=now,
        session_name="persisted-session",
        input_filename="novel.txt",
        request=WebRunRequest(chapters=1, start_chapter=1),
        progress=WebRunProgress(total_steps=5, completed_steps=5, message="运行完成"),
        input_path="novel.txt",
        log_messages=["任务已创建", "运行完成"],
    )
    run_path = settings.web_runs_dir / "persisted-run.json"
    run_path.write_text(run.model_dump_json(indent=2), encoding="utf-8")

    manager = WebRunManager(settings)
    runs = manager.list_runs()

    assert len(runs) == 1
    assert runs[0].id == "persisted-run"
    assert manager.get_run("persisted-run").session_name == "persisted-session"


def test_web_run_manager_decodes_gbk_upload(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)

    input_path, suggested_name = manager.save_uploaded_text(
        "斗破苍穹.txt",
        "第一章 陨落的天才".encode("gbk"),
    )

    assert suggested_name == "novel"
    assert input_path.exists()
    assert "第一章 陨落的天才" in input_path.read_text(encoding="utf-8")
