from __future__ import annotations

import asyncio
import threading
from datetime import datetime, timezone
from pathlib import Path

from config.settings import AppSettings
from core.benchmarking.runner import BenchmarkReport, CandidateReport, CandidateScore, PairwiseJudgement
from core.llm.litellm_client import LLMUsageSummary
from core.models.arc_outline import ArcOutline
from core.models.chapter_brief import ChapterBrief
from core.models.evaluation import ChapterEvaluation, EvaluationScore
from core.models.lorebook import LorebookBundle
from core.models.reference_profile import ReferenceProfile
from core.models.story_state import StoryWorldState
from core.models.style_profile import ExtractionSnapshot, StyleProfile
from core.models.world_model import WorldModel
from orchestrator import ChapterRunResult, PipelineRunResult
from pipeline.stage1_extraction.novel_indexer import IndexingResult
from webapp.manager import WebRunManager
from webapp.models import WebRunDetail, WebRunProgress, WebRunRequest, WebRuntimeApiOverride


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
    input_path = settings.web_uploads_dir / "demo.txt"
    input_path.write_text(
        "第一章 测试\n\n沈照站在义庄门口。\n\n雨越下越大。\n\n一队人已经到了门外。",
        encoding="utf-8",
    )

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
            input_path=str(input_path),
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
        input_path=str(input_path),
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
    assert detail.latest_source_preview_label == "原文断点"
    assert "一队人已经到了门外" in (detail.latest_source_preview or "")


def test_web_run_manager_lists_benchmarks(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)
    report_dir = settings.benchmarks_dir / "demo" / "cases" / "1_to_2" / "report"
    report_dir.mkdir(parents=True, exist_ok=True)
    report = BenchmarkReport(
        dataset_name="demo",
        case_name="1_to_2",
        prefix_chapter_count=1,
        target_chapter_number=2,
        source_path="source.txt",
        prefix_path="prefix.txt",
        reference_path="reference.txt",
        system_session_name="demo-session",
        system_manifest_path="manifest.json",
        system_output_path="system.md",
        baseline_output_path="baseline.md",
        pairwise=PairwiseJudgement(winner="system", confidence=0.9, reasoning=["更稳", "更像原著"]),
        system_report=CandidateReport(
            label="system",
            output_path="system.md",
            score=CandidateScore(
                plot_alignment=0.9,
                character_consistency=0.9,
                style_similarity=0.8,
                readability=0.8,
                overall=0.85,
                strengths=["剧情推进稳"],
                weaknesses=["爆点稍弱"],
                summary="更稳",
            ),
            elapsed_seconds=12.3,
        ),
        baseline_report=CandidateReport(
            label="baseline",
            output_path="baseline.md",
            score=CandidateScore(
                plot_alignment=0.6,
                character_consistency=0.6,
                style_similarity=0.6,
                readability=0.6,
                overall=0.6,
                strengths=["语言顺"],
                weaknesses=["偏离原著"],
                summary="一般",
            ),
            elapsed_seconds=8.4,
        ),
        total_usage=LLMUsageSummary(total_tokens=1234, total_cost_usd=0.12),
        report_markdown_path=str(report_dir / "benchmark_report.md"),
        report_json_path=str(report_dir / "benchmark_report.json"),
    )
    (report_dir / "benchmark_report.json").write_text(report.model_dump_json(indent=2), encoding="utf-8")

    summaries = manager.list_benchmarks()
    detail = manager.get_benchmark("demo", "1_to_2")

    assert summaries[0].dataset_name == "demo"
    assert summaries[0].winner == "system"
    assert detail.system_score == 0.85
    assert detail.system_strengths == ["剧情推进稳"]
    assert detail.baseline_weaknesses == ["偏离原著"]
    assert detail.pairwise_reasoning == ["更稳", "更像原著"]


def test_web_run_manager_builds_run_settings_with_model_overrides(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    settings.web_model_options = "deepseek/deepseek-chat,openai/gpt-4.1-mini"
    manager = WebRunManager(settings)

    request = WebRunRequest(
        style_model="openai/gpt-4.1-mini",
        plot_model="openai/gpt-4.1-mini",
        draft_model="deepseek/deepseek-chat",
        quality_model="deepseek/deepseek-chat",
        lightrag_model_name="openai/gpt-4.1-mini",
    )

    runtime = manager.get_runtime_config()
    run_settings = manager._settings_for_request(
        request,
        WebRuntimeApiOverride(
            api_base_url="https://openrouter.ai/api/v1",
            api_key="sk-demo",
        ),
    )

    assert "openai/gpt-4.1-mini" in runtime.model_options
    assert runtime.api_base_url == "https://api.deepseek.com"
    assert run_settings.models.style_model == "openai/gpt-4.1-mini"
    assert run_settings.models.plot_model == "openai/gpt-4.1-mini"
    assert run_settings.models.lightrag_model_name == "openai/gpt-4.1-mini"
    assert run_settings.runtime_api_base_url == "https://openrouter.ai/api/v1"
    assert run_settings.runtime_api_key == "sk-demo"
    assert settings.models.style_model == "deepseek/deepseek-chat"
    assert settings.runtime_api_key is None


def test_web_run_manager_lists_examples(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)

    examples = manager.list_examples()

    assert examples[0].id == "sample_novel"
    assert examples[0].input_filename == "sample_novel.txt"
    assert "首次打开就能试跑" in examples[0].description
    assert examples[0].source_excerpt is not None


def test_web_run_manager_backfills_source_preview_for_persisted_legacy_run(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    input_path = settings.web_uploads_dir / "legacy.txt"
    input_path.write_text(
        "第一章 雨夜\n\n沈照听见门外马蹄声。\n\n院中风灯摇晃不定。",
        encoding="utf-8",
    )
    run = WebRunDetail(
        id="legacy-run",
        status="completed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        session_name="legacy",
        input_filename="legacy.txt",
        request=WebRunRequest(chapters=1, start_chapter=1),
        progress=WebRunProgress(total_steps=5, completed_steps=5, message="运行完成"),
        input_path=str(input_path),
        output_paths=["chapter_1.md"],
        latest_output_preview="示例正文",
    )
    (settings.web_runs_dir / "legacy-run.json").write_text(
        run.model_dump_json(indent=2),
        encoding="utf-8",
    )

    manager = WebRunManager(settings)
    detail = manager.get_run("legacy-run")

    assert detail.latest_source_preview_label == "原文断点"
    assert "院中风灯摇晃不定" in (detail.latest_source_preview or "")


def test_web_run_manager_gets_builtin_example_detail(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)

    example = manager.get_example("sample_novel")

    assert example.id == "sample_novel"
    assert "沈照" in example.text_content
    assert example.trial_limit_note is not None


def test_web_run_manager_reads_full_source_text(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)
    input_path = settings.web_uploads_dir / "demo.txt"
    input_text = "第一章 雨夜追魂\n\n沈照站在义庄门口。\n\n门外雷声炸响。"
    input_path.write_text(input_text, encoding="utf-8")

    run = WebRunDetail(
        id="run-1",
        status="completed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        session_name="demo-session",
        input_filename="demo.txt",
        request=WebRunRequest(chapters=1, start_chapter=1),
        progress=WebRunProgress(total_steps=5, completed_steps=5),
        input_path=str(input_path),
    )
    manager._runs["run-1"] = run

    source = manager.get_run_source_text("run-1")

    assert source.input_filename == "demo.txt"
    assert source.text_content == input_text
    assert source.character_count == len(input_text)


def test_web_run_manager_builds_public_showcase_from_builtin_fallback(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)

    showcase = manager.get_public_showcase()

    assert showcase is not None
    assert showcase.title == "原创悬疑样例 · 公开可展示"
    assert "AI 续写片段" in showcase.output_label


def test_web_run_manager_builds_public_showcase_from_original_sample(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)

    sample_path = settings.input_dir / "sample_novel.txt"
    sample_path.parent.mkdir(parents=True, exist_ok=True)
    sample_path.write_text(
        "第一章 雨夜追魂\n\n沈照站在义庄门口。\n\n门外雷声炸响。\n\n铺门已经被人一脚踹开。",
        encoding="utf-8",
    )
    output_dir = settings.output_dir / "sample_novel-demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "chapter_1.md").write_text(
        "## 第一章\n\n雨停了。\n\n沈照反手闩上门。\n\n他们终于在旧货栈碰头。",
        encoding="utf-8",
    )
    session_dir = settings.sessions_dir / "sample_novel-demo"
    session_dir.mkdir(parents=True, exist_ok=True)
    (session_dir / "chapter_1_evaluation.json").write_text(
        ChapterEvaluation(
            chapter_number=1,
            score=EvaluationScore(
                continuity_score=0.9,
                character_score=0.84,
                world_consistency_score=0.9,
                novelty_score=0.95,
                arc_progress_score=0.95,
            ),
            summary="推进稳定。",
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    (session_dir / "chapter_1_brief.json").write_text(
        ChapterBrief(chapter_number=1, chapter_goal="先推进冲突").model_dump_json(indent=2),
        encoding="utf-8",
    )

    showcase = manager.get_public_showcase()

    assert showcase is not None
    assert showcase.title == "原创悬疑样例 · 公开可展示"
    assert "原著断点" in showcase.source_label
    assert "AI 续写片段" in showcase.output_label
    assert showcase.chapter_goal == "先推进冲突"
    assert showcase.evaluation_summary == "推进稳定。"
    assert showcase.continuity_score == 0.9


def test_web_run_manager_starts_builtin_example_without_disk_sample(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)
    captured: dict[str, object] = {}

    def fake_schedule(run_id: str, run_settings: AppSettings | None = None) -> None:
        captured["run_id"] = run_id
        captured["run_settings"] = run_settings

    manager._schedule_run = fake_schedule  # type: ignore[method-assign]

    summary = manager.start_example_run(
        example_id="sample_novel",
        request=WebRunRequest(chapters=1, start_chapter=1),
    )

    assert summary.input_filename == "sample_novel.txt"
    assert summary.session_name.startswith("sample_novel-")
    assert summary.session_name != "sample_novel-demo"
    uploaded_files = list(settings.web_uploads_dir.glob("sample_novel-*.txt"))
    assert len(uploaded_files) == 1
    assert "沈照" in uploaded_files[0].read_text(encoding="utf-8")


def test_web_run_manager_loads_precomputed_example_preview_run(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)

    input_path = settings.input_dir / "sample_novel.txt"
    input_path.parent.mkdir(parents=True, exist_ok=True)
    input_path.write_text(
        "第一章 雨夜追魂\n\n沈照站在义庄门口。\n\n门外雷声炸响。\n\n铺门已经被人一脚踹开。",
        encoding="utf-8",
    )
    session_dir = settings.sessions_dir / "sample_novel-demo"
    session_dir.mkdir(parents=True, exist_ok=True)
    output_dir = settings.output_dir / "sample_novel-demo"
    output_dir.mkdir(parents=True, exist_ok=True)
    snapshot_path = session_dir / "stage1_snapshot.json"
    snapshot_path.write_text(
        ExtractionSnapshot(
            style_profile=StyleProfile(summary="冷峻悬疑"),
            story_state=StoryWorldState(summary="旧案被重新翻起"),
        ).model_dump_json(indent=2),
        encoding="utf-8",
    )
    output_path = output_dir / "chapter_1.md"
    output_path.write_text(
        "## 第一章\n\n雨停了。\n\n沈照反手闩上门。\n\n他们终于在旧货栈碰头。",
        encoding="utf-8",
    )
    (session_dir / "chapter_1_brief.json").write_text(
        ChapterBrief(chapter_number=1, chapter_goal="先推进冲突").model_dump_json(indent=2),
        encoding="utf-8",
    )
    (session_dir / "chapter_1_evaluation.json").write_text(
        ChapterEvaluation(chapter_number=1, summary="推进稳定。").model_dump_json(indent=2),
        encoding="utf-8",
    )
    manifest = PipelineRunResult(
        session_name="sample_novel-demo",
        input_path=str(input_path),
        stage1_snapshot_path=str(snapshot_path),
        index_result=IndexingResult(
            source_path=str(input_path),
            chunk_count=4,
            character_count=len(input_path.read_text(encoding="utf-8")),
        ),
        chapters=[
            ChapterRunResult(
                chapter_number=1,
                skeleton_path=str(session_dir / "chapter_1_skeleton.json"),
                draft_path=str(session_dir / "chapter_1_draft.md"),
                output_path=str(output_path),
                chapter_goal="先推进冲突",
            )
        ],
    )
    (session_dir / "run_manifest.json").write_text(
        manifest.model_dump_json(indent=2),
        encoding="utf-8",
    )

    summary = manager.load_example_preview_run(example_id="sample_novel")
    detail = manager.get_run(summary.id)

    assert summary.id == "example-preview-sample_novel"
    assert detail.status == "completed"
    assert detail.session_name == "sample_novel-demo"
    assert detail.request.use_existing_index is True
    assert detail.progress.message == "已加载预计算样例结果"
    assert detail.latest_source_preview_label == "原文断点"
    assert "铺门已经被人一脚踹开" in (detail.latest_source_preview or "")
    assert "雨停了" in (detail.latest_output_preview or "")
    assert detail.latest_chapter_brief["chapter_goal"] == "先推进冲突"


def test_web_run_manager_preserves_explicit_example_session_name(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)
    captured: dict[str, object] = {}

    def fake_schedule(run_id: str, run_settings: AppSettings | None = None) -> None:
        captured["run_id"] = run_id
        captured["run_settings"] = run_settings

    manager._schedule_run = fake_schedule  # type: ignore[method-assign]

    summary = manager.start_example_run(
        example_id="sample_novel",
        request=WebRunRequest(session_name="manual-preview-check", chapters=1, start_chapter=1),
    )

    assert summary.session_name == "manual-preview-check"


def test_web_run_manager_uses_previous_output_as_source_preview_for_later_chapter(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)
    input_path = settings.web_uploads_dir / "demo.txt"
    input_path.write_text("第一章 原文", encoding="utf-8")
    session_dir = settings.sessions_dir / "demo-session"
    session_dir.mkdir(parents=True, exist_ok=True)
    output_dir = settings.output_dir / "demo-session"
    output_dir.mkdir(parents=True, exist_ok=True)
    chapter_1_output = output_dir / "chapter_1.md"
    chapter_2_output = output_dir / "chapter_2.md"
    chapter_1_output.write_text(
        "# 第一章\n\n沈照在门前停住。\n\n铜扣还在掌心发凉。",
        encoding="utf-8",
    )
    chapter_2_output.write_text("# 第二章\n\n顾行舟推门而入。", encoding="utf-8")
    snapshot_path = session_dir / "stage1_snapshot.json"
    snapshot_path.write_text(
        '{"style_profile":{"summary":"测试风格"},"story_state":{"summary":"测试故事"}}',
        encoding="utf-8",
    )

    run = WebRunDetail(
        id="run-1",
        status="completed",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
        session_name="demo-session",
        input_filename="demo.txt",
        request=WebRunRequest(chapters=2, start_chapter=1),
        progress=WebRunProgress(total_steps=5, completed_steps=5),
        input_path=str(input_path),
        stage1_snapshot_path=str(snapshot_path),
    )
    manager._runs["run-1"] = run

    manager._populate_outputs(
        "run-1",
        type(
            "PipelineResult",
            (),
            {
                "session_name": "demo-session",
                "stage1_snapshot_path": str(snapshot_path),
                "chapters": [
                    type(
                        "ChapterResult",
                        (),
                        {
                            "chapter_number": 1,
                            "status": "completed",
                            "chapter_goal": "起冲突",
                            "output_path": str(chapter_1_output),
                            "quality_report": None,
                            "consistency_report": None,
                            "elapsed_seconds": 1.0,
                            "skeleton_path": None,
                            "draft_path": None,
                        },
                    )(),
                    type(
                        "ChapterResult",
                        (),
                        {
                            "chapter_number": 2,
                            "status": "completed",
                            "chapter_goal": "推剧情",
                            "output_path": str(chapter_2_output),
                            "quality_report": None,
                            "consistency_report": None,
                            "elapsed_seconds": 1.0,
                            "skeleton_path": None,
                            "draft_path": None,
                        },
                    )(),
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

    assert detail.latest_source_preview_label == "上文衔接"
    assert "铜扣还在掌心发凉" in (detail.latest_source_preview or "")


def test_web_run_manager_reuses_background_event_loop(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)
    input_path = settings.web_uploads_dir / "demo.txt"
    input_path.write_text("第一章 测试", encoding="utf-8")

    loop_ids: list[int] = []
    finished = threading.Event()

    async def fake_run_pipeline(
        self: WebRunManager,
        run_id: str,
        run_settings: AppSettings | None = None,
    ) -> None:
        loop_ids.append(id(asyncio.get_running_loop()))
        assert run_settings is not None
        current = self.get_run(run_id)
        self._update_run(
            run_id,
            status="completed",
            progress=current.progress.model_copy(
                update={
                    "completed_steps": current.progress.total_steps,
                    "message": "运行完成",
                }
            ),
        )
        if len(loop_ids) == 2:
            finished.set()

    manager._run_pipeline_async = fake_run_pipeline.__get__(manager, WebRunManager)

    manager.start_run(
        input_path=input_path,
        input_filename="demo.txt",
        request=WebRunRequest(chapters=1, start_chapter=1),
    )
    manager.start_run(
        input_path=input_path,
        input_filename="demo.txt",
        request=WebRunRequest(chapters=1, start_chapter=1),
    )

    assert finished.wait(timeout=2)
    assert len(loop_ids) == 2
    assert len(set(loop_ids)) == 1


def test_web_run_manager_does_not_persist_runtime_api_override(tmp_path: Path) -> None:
    settings = build_settings(tmp_path)
    manager = WebRunManager(settings)
    input_path = settings.web_uploads_dir / "demo.txt"
    input_path.write_text("第一章 测试", encoding="utf-8")

    captured: dict[str, AppSettings] = {}

    def fake_schedule(run_id: str, run_settings: AppSettings | None = None) -> None:
        captured["run_id"] = run_id
        captured["settings"] = run_settings

    manager._schedule_run = fake_schedule  # type: ignore[method-assign]

    summary = manager.start_run(
        input_path=input_path,
        input_filename="demo.txt",
        request=WebRunRequest(chapters=1, start_chapter=1),
        runtime_api_override=WebRuntimeApiOverride(
            api_base_url="https://openrouter.ai/api/v1",
            api_key="sk-demo",
        ),
    )

    persisted = (settings.web_runs_dir / f"{summary.id}.json").read_text(encoding="utf-8")

    assert "sk-demo" not in persisted
    assert "openrouter.ai" not in persisted
    assert captured["settings"].runtime_api_key == "sk-demo"
