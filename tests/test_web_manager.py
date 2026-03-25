from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from config.settings import AppSettings
from core.models.arc_outline import ArcOutline
from core.models.chapter_brief import ChapterBrief
from core.models.evaluation import ChapterEvaluation
from core.models.lorebook import LorebookBundle
from core.models.reference_profile import ReferenceProfile
from core.models.world_model import WorldModel
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


def test_web_run_manager_loads_workspace_artifacts(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)
    session_dir = settings.sessions_dir / "demo-session"
    session_dir.mkdir(parents=True, exist_ok=True)

    (session_dir / "run_manifest.json").write_text(
        WebRunDetail(
            id="run-1",
            status="completed",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            session_name="demo-session",
            input_filename="demo.txt",
            request=WebRunRequest(chapters=1, start_chapter=1),
            progress=WebRunProgress(total_steps=5, completed_steps=5),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    (session_dir / "stage1_snapshot.json").write_text(
        '{"style_profile":{"summary":"沉稳"},"story_state":{"summary":"旧案重启"}}',
        encoding="utf-8",
    )
    (session_dir / "world_model.json").write_text(
        WorldModel(summary="世界扩张").model_dump_json(indent=2),
        encoding="utf-8",
    )
    (session_dir / "lorebook.json").write_text(
        LorebookBundle().model_dump_json(indent=2),
        encoding="utf-8",
    )
    (session_dir / "selected_references.json").write_text(
        '{"profiles":[{"name":"世界扩张参考","reference_type":"world"}]}',
        encoding="utf-8",
    )
    (session_dir / "chapter_1_brief.json").write_text(
        ChapterBrief(chapter_number=1, chapter_goal="拿到线索").model_dump_json(indent=2),
        encoding="utf-8",
    )
    (session_dir / "chapter_1_evaluation.json").write_text(
        ChapterEvaluation(chapter_number=1, summary="推进稳定").model_dump_json(indent=2),
        encoding="utf-8",
    )
    candidates_dir = session_dir / "candidates"
    candidates_dir.mkdir(exist_ok=True)
    (candidates_dir / "chapter_1_skeleton_candidate_1.json").write_text("{}", encoding="utf-8")
    (candidates_dir / "chapter_1_draft_candidate_1.md").write_text("候选正文", encoding="utf-8")
    arcs_dir = session_dir / "arcs"
    arcs_dir.mkdir(exist_ok=True)
    (arcs_dir / "arc_0001_0003.json").write_text(
        ArcOutline(
            arc_id="arc_0001_0003",
            arc_theme="旧案发酵",
            arc_goal="把冲突推到台前",
            chapters_span=[1, 3],
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )

    result = WebRunDetail(
        id="run-1",
        status="completed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        session_name="demo-session",
        input_filename="demo.txt",
        request=WebRunRequest(chapters=1, start_chapter=1),
        progress=WebRunProgress(total_steps=5, completed_steps=5),
        stage1_snapshot_path=str(session_dir / "stage1_snapshot.json"),
    )
    manager._runs["run-1"] = result
    manager._populate_outputs(
        "run-1",
        type(
            "PipelineResult",
            (),
            {
                "session_name": "demo-session",
                "stage1_snapshot_path": str(session_dir / "stage1_snapshot.json"),
                "chapters": [
                    type(
                        "ChapterResult",
                        (),
                        {
                            "chapter_number": 1,
                            "status": "completed",
                            "chapter_goal": "拿到线索",
                            "output_path": None,
                            "quality_report": None,
                            "consistency_report": None,
                            "elapsed_seconds": 1.2,
                            "skeleton_path": str(session_dir / "chapter_1_skeleton.json"),
                            "draft_path": str(session_dir / "chapter_1_draft.md"),
                        },
                    )()
                ],
                "total_usage": type(
                    "Usage",
                    (),
                    {
                        "calls": 0,
                        "total_tokens": 0,
                        "total_cost_usd": 0.0,
                    },
                )(),
            },
        )(),
    )

    detail = manager.get_run("run-1")

    assert detail.world_model["summary"] == "世界扩张"
    assert detail.selected_references[0]["name"] == "世界扩张参考"
    assert detail.arc_outlines[0]["arc_id"] == "arc_0001_0003"
    assert detail.latest_chapter_brief["chapter_goal"] == "拿到线索"
    assert detail.latest_chapter_evaluation["summary"] == "推进稳定"
    assert detail.latest_skeleton_candidate_paths[0].endswith("chapter_1_skeleton_candidate_1.json")
    assert detail.latest_draft_candidate_paths[0].endswith("chapter_1_draft_candidate_1.md")
