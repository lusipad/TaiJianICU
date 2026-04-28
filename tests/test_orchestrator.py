from datetime import datetime, timezone

from config.settings import AppSettings, RuntimeTuning
from core.models.chapter_brief import ChapterBrief
from core.models.revival import DirectorArcOption
from core.models.story_state import StoryThread
from core.llm.litellm_client import LLMUsageSummary
from core.storage.session_store import SessionStore
from intervention import InterventionConfig
from orchestrator import ChapterRunResult, PipelineRunResult, TaiJianOrchestrator
from pipeline.stage1_extraction.novel_indexer import IndexingResult


def build_usage(*, calls: int, total_tokens: int, total_cost_usd: float) -> LLMUsageSummary:
    return LLMUsageSummary(
        calls=calls,
        prompt_tokens=total_tokens // 2,
        completion_tokens=total_tokens - total_tokens // 2,
        total_tokens=total_tokens,
        total_cost_usd=total_cost_usd,
        by_model={
            "deepseek/deepseek-chat": {
                "calls": calls,
                "prompt_tokens": total_tokens // 2,
                "completion_tokens": total_tokens - total_tokens // 2,
                "total_tokens": total_tokens,
                "cached_tokens": 0,
                "total_cost_usd": total_cost_usd,
            }
        },
    )


def test_revival_analysis_rejects_too_short_source(tmp_path) -> None:
    input_path = tmp_path / "tiny.txt"
    input_path.write_text("沈照站在雨里。", encoding="utf-8")

    try:
        TaiJianOrchestrator._validate_revival_source_text(input_path)
    except ValueError as exc:
        assert "文本太短，无法提取作品声纹" in str(exc)
    else:
        raise AssertionError("short revival source should fail")


def test_build_session_manifest_preserves_existing_resume_details(tmp_path) -> None:
    orchestrator = TaiJianOrchestrator.__new__(TaiJianOrchestrator)
    orchestrator.session_store = SessionStore(tmp_path)

    previous_stage1 = build_usage(calls=1, total_tokens=1000, total_cost_usd=0.001)
    previous_chapter = ChapterRunResult(
        chapter_number=1,
        skeleton_path="chapter_1_skeleton.json",
        draft_path="chapter_1_draft.md",
        output_path="chapter_1.md",
        status="completed",
        chapter_goal="旧目标",
        usage_summary=build_usage(calls=3, total_tokens=2000, total_cost_usd=0.002),
    )
    previous_result = PipelineRunResult(
        session_name="demo",
        input_path="data/input/sample_novel.txt",
        stage1_snapshot_path="stage1_snapshot.json",
        index_result=IndexingResult(
            source_path="data/input/sample_novel.txt",
            chunk_count=2,
            character_count=1234,
        ),
        stage1_usage=previous_stage1,
        chapters=[previous_chapter],
        total_usage=TaiJianOrchestrator._merge_usage_summaries(
            previous_stage1,
            previous_chapter.usage_summary,
        ),
        started_at=datetime(2026, 3, 25, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 25, tzinfo=timezone.utc),
    )
    orchestrator.session_store.save_model(
        orchestrator.session_store.run_manifest_path("demo"),
        previous_result,
    )

    current_result = PipelineRunResult(
        session_name="demo",
        input_path="data/input/sample_novel.txt",
        stage1_snapshot_path="stage1_snapshot.json",
        index_result=IndexingResult(
            source_path="data/input/sample_novel.txt",
            chunk_count=0,
            character_count=1234,
        ),
        chapters=[
            ChapterRunResult(
                chapter_number=1,
                skeleton_path="chapter_1_skeleton.json",
                draft_path="chapter_1_draft.md",
                output_path="chapter_1.md",
                status="skipped_existing_output",
                chapter_goal="新目标",
            )
        ],
        started_at=datetime(2026, 3, 26, tzinfo=timezone.utc),
        finished_at=datetime(2026, 3, 26, tzinfo=timezone.utc),
    )

    merged = orchestrator._build_session_manifest("demo", current_result)

    assert merged.stage1_usage.total_tokens == previous_stage1.total_tokens
    assert merged.total_usage.total_tokens == previous_result.total_usage.total_tokens
    assert merged.index_result.chunk_count == 2
    assert merged.chapters[0].usage_summary.total_tokens == previous_chapter.usage_summary.total_tokens
    assert merged.chapters[0].status == "completed"
    assert merged.chapters[0].chapter_goal == "旧目标"


def test_apply_chapter_brief_overrides_and_build_goal() -> None:
    orchestrator = TaiJianOrchestrator.__new__(TaiJianOrchestrator)
    chapter_brief = ChapterBrief(
        chapter_number=12,
        chapter_goal="把暗线推到台前",
        chapter_note="需要稳住悬念",
        must_happen=["主角拿到线索"],
        must_not_break=["黑玉不能突然完整出现"],
    )

    merged = orchestrator._apply_chapter_brief_overrides(
        chapter_brief=chapter_brief,
        intervention_must_happen=["反派必须露面"],
        intervention_notes="别写成正面冲突",
        goal_hint="逼近真相但不彻底揭底",
    )
    goal = orchestrator._build_chapter_goal(
        chapter_brief=merged,
        focus_threads=[
            StoryThread(id="T001", description="黑玉去向", introduced_at=1, last_advanced=11)
        ],
    )

    assert merged.chapter_goal == "逼近真相但不彻底揭底"
    assert merged.must_happen == ["主角拿到线索", "反派必须露面"]
    assert "人工备注：别写成正面冲突" in merged.chapter_note
    assert "必须发生：主角拿到线索；反派必须露面" in goal
    assert "优先推进伏笔：T001:黑玉去向" in goal
    assert "不可破坏设定：黑玉不能突然完整出现" in goal


def test_apply_selected_arc_to_chapter_brief() -> None:
    orchestrator = TaiJianOrchestrator.__new__(TaiJianOrchestrator)
    brief = ChapterBrief(
        chapter_number=1,
        chapter_goal="推进主线",
        chapter_note="保持慢热",
        must_happen=["主角拿到线索"],
        must_not_break=["黑玉不能完整出现"],
    )

    merged = orchestrator._apply_selected_arc_to_brief(
        chapter_brief=brief,
        selected_option=DirectorArcOption(
            id="arc_a",
            title="暗压升温",
            emotional_direction="让关系压力升温",
            must_happen=["反派露面"],
            must_not_break=["不能直接揭底"],
        ),
    )

    assert "导演弧线：暗压升温" in merged.chapter_note
    assert merged.must_happen == ["主角拿到线索", "反派露面"]
    assert merged.must_not_break == ["黑玉不能完整出现", "不能直接揭底"]


def test_settings_candidate_counts_can_be_overridden() -> None:
    settings = AppSettings(
        tuning=RuntimeTuning(
            skeleton_candidate_count=2,
            draft_candidate_count=3,
        )
    )

    assert settings.tuning.skeleton_candidate_count == 2
    assert settings.tuning.draft_candidate_count == 3
