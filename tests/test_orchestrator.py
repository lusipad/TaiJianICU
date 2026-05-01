from datetime import datetime, timezone

from config.settings import AppSettings, RuntimeTuning
from core.models.arc_outline import ArcOutline
from core.models.chapter_brief import ChapterBrief, ExpansionBudget
from core.models.lorebook import LorebookBundle
from core.models.revival import (
    BlindChallenge,
    BlindChallengeExcerpt,
    BlindJudgeDecision,
    BlindJudgeReport,
    BlindJudgeRound,
    DirectorArcOption,
    DirectorArcOptions,
    RevivalChapter,
    RevivalStyleBible,
    RevivalWorkspaceArtifacts,
    SelectedArc,
    StyleMetrics,
)
from core.models.skeleton import ChapterSkeleton, SceneNode
from core.models.story_state import StoryThread, StoryWorldState
from core.models.style_profile import ExtractionSnapshot, StyleProfile
from core.models.world_model import WorldModel
from core.llm.litellm_client import LLMUsageSummary
from core.storage.session_store import SessionStore
from intervention import InterventionConfig
from orchestrator import ChapterRunResult, PipelineRunResult, PreparedStoryContext, TaiJianOrchestrator
from pipeline.revival import CleanProseGate, CleanProseGateResult, RevivalDiagnosisBuilder
from pipeline.stage2_plot.consistency_checker import ConsistencyReport
from pipeline.stage3_generation.quality_checker import QualityReport
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


class _FakeUsageService:
    def usage_mark(self) -> int:
        return 0

    def usage_summary(
        self,
        start_index: int = 0,
        end_index: int | None = None,
    ) -> LLMUsageSummary:
        return LLMUsageSummary()


class _FakeChapterAllocator:
    def allocate(self, **kwargs) -> ChapterBrief:
        return ChapterBrief(
            chapter_number=kwargs["chapter_number"],
            chapter_goal="让旧事浮出水面",
        )


class _FakeIntervention:
    def load_or_create(self, session_name: str, chapter_number: int) -> InterventionConfig:
        return InterventionConfig()


class _FakeLorebookManager:
    def match(self, *, lorebook: LorebookBundle, query_text: str) -> LorebookBundle:
        return lorebook


class _FakeStyleSampler:
    async def sample(self, *args, **kwargs) -> list[str]:
        return []


class _FakeChapterGenerator:
    def __init__(self) -> None:
        self.revise_calls = []

    async def revise(self, **kwargs) -> str:
        self.revise_calls.append(kwargs)
        return "改后正文。"


class _FakeFinalizeChapterGenerator:
    async def polish(self, **kwargs) -> str:
        return "本章推进宝玉的人物弧光。众人沉默。"

    async def revise(self, **kwargs) -> str:
        return "话说宝玉进来，笑道：“你且听我说。”众人一面说笑，一面看那阶前花影。" * 80


class _FakeQualityChecker:
    def __init__(self) -> None:
        self.evaluated_texts: list[str] = []

    async def evaluate(self, **kwargs) -> QualityReport:
        self.evaluated_texts.append(kwargs["draft_text"])
        return QualityReport(score=0.9, verdict="pass")


class _TrackingCleanGate:
    def __init__(self) -> None:
        self.checked_texts: list[str] = []

    def check(self, text: str) -> CleanProseGateResult:
        self.checked_texts.append(text)
        return CleanProseGateResult(status="pass", chinese_char_count=1000)


class _TrackingBlindChallengeBuilder:
    def __init__(self) -> None:
        self.texts: list[str] = []

    def build(
        self,
        chapter_text: str,
        *,
        source_chapters: list[RevivalChapter] | None = None,
    ) -> BlindChallenge:
        self.texts.append(chapter_text)
        excerpts = [
            BlindChallengeExcerpt(
                excerpt_id=label,
                text=f"{label}:{chapter_text}",
                excerpt_char_count=1000,
            )
            for label in ("A", "B", "C", "D")
        ]
        return BlindChallenge(
            excerpt_text=chapter_text,
            excerpt_char_count=1000,
            excerpts=excerpts,
            generated_excerpt_id="A",
        )


class _FailingBlindJudge:
    def __init__(self) -> None:
        self.round_numbers: list[int] = []

    async def judge(
        self,
        *,
        challenge: BlindChallenge,
        style_bible: RevivalStyleBible,
        round_number: int,
    ) -> BlindJudgeRound:
        self.round_numbers.append(round_number)
        decision = BlindJudgeDecision(
            suspected_excerpt_id=challenge.generated_excerpt_id or "",
            confidence=0.95,
            reason="句法太现代",
        )
        return BlindJudgeRound(
            round_number=round_number,
            generated_excerpt_id=challenge.generated_excerpt_id,
            decision=decision,
            passed=False,
            failure_reasons=["句法太现代"],
        )

    def report(
        self,
        *,
        rounds: list[BlindJudgeRound],
        confidence_threshold: float,
    ) -> BlindJudgeReport:
        return BlindJudgeReport(
            status="fail",
            confidence_threshold=confidence_threshold,
            rounds=rounds,
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


def test_clean_prose_gate_for_workspace_uses_style_bible() -> None:
    orchestrator = TaiJianOrchestrator.__new__(TaiJianOrchestrator)
    orchestrator.clean_prose_gate = CleanProseGate(min_chinese_chars=1000)
    metrics = StyleMetrics(
        chinese_char_count=2000,
        avg_sentence_length=12,
        dialogue_ratio=0.3,
        function_word_density={"的": 0.01},
    )
    workspace = RevivalWorkspaceArtifacts(
        source_digest="abc123",
        style_bible=RevivalStyleBible(
            generated_at=datetime.now(timezone.utc),
            style_metrics=metrics,
            forbidden_words=["安全感"],
        ),
    )

    gate = orchestrator._clean_prose_gate_for_workspace(workspace)

    assert gate.forbidden_words == ["安全感"]
    assert gate.style_metrics == metrics


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


async def test_finalize_output_revises_source_voice_gate_failures(tmp_path) -> None:
    settings = AppSettings(
        output_dir=tmp_path / "output",
        sessions_dir=tmp_path / "sessions",
        tuning=RuntimeTuning(quality_retry_limit=1),
    )
    source = "\n\n".join(
        [
            f"第{number}回 旧事\n话说宝玉进来，笑道：“你且听我说。”"
            + "众人一面说笑，一面看那阶前花影。" * 80
            for number in ("一", "二", "三")
        ]
    )
    input_path = tmp_path / "source.txt"
    input_path.write_text(source, encoding="utf-8")
    skeleton = ChapterSkeleton(
        chapter_number=4,
        chapter_theme="旧事",
        scenes=[
            SceneNode(
                scene_type="interior",
                participants=["宝玉"],
                scene_purpose="旧事重提",
            )
        ],
    )
    quality_checker = _FakeQualityChecker()
    chapter_generator = _FakeFinalizeChapterGenerator()
    orchestrator = TaiJianOrchestrator.__new__(TaiJianOrchestrator)
    orchestrator.settings = settings
    orchestrator.chapter_generator = chapter_generator
    orchestrator.quality_checker = quality_checker
    orchestrator._source_voice_gate = TaiJianOrchestrator._source_voice_gate.__get__(
        orchestrator,
        TaiJianOrchestrator,
    )

    final_text, quality_report = await orchestrator._finalize_output(
        session_name="demo",
        chapter_number=4,
        skeleton=skeleton,
        world_model=WorldModel(),
        chapter_brief=ChapterBrief(chapter_number=4, chapter_goal="旧事重提"),
        lorebook_context=LorebookBundle(),
        snapshot=ExtractionSnapshot(
            style_profile=StyleProfile(),
            story_state=StoryWorldState(title="红楼梦"),
        ),
        draft_text="草稿正文。",
        style_samples=[],
        source_text=source,
    )

    assert "本章推进" not in final_text
    assert quality_report.verdict == "pass"
    assert quality_checker.evaluated_texts == [
        "本章推进宝玉的人物弧光。众人沉默。",
        final_text,
    ]


async def test_revival_generation_rewrites_and_persists_blind_judge_failure(tmp_path) -> None:
    settings = AppSettings(
        output_dir=tmp_path / "output",
        sessions_dir=tmp_path / "sessions",
        tuning=RuntimeTuning(blind_judge_retry_limit=1),
    )
    store = SessionStore(settings.sessions_dir)
    input_path = tmp_path / "source.txt"
    input_path.write_text("第八十回 旧事\n" + "原文片段。" * 400, encoding="utf-8")
    now = datetime.now(timezone.utc)
    style_bible = RevivalStyleBible(
        generated_at=now,
        style_metrics=StyleMetrics(chinese_char_count=2000),
    )
    workspace = RevivalWorkspaceArtifacts(
        source_digest="abc123",
        chapters=[
            RevivalChapter(
                chapter_number=80,
                title="旧事",
                text="原文片段。" * 400,
                start_char=0,
                end_char=2000,
            )
        ],
        style_bible=style_bible,
    )
    selected_option = DirectorArcOption(
        id="arc_a",
        title="旧事浮现",
        must_happen=["旧事浮出水面"],
    )
    store.save_model(
        store.arc_options_path("demo"),
        DirectorArcOptions(
            generated_at=now,
            options=[
                selected_option,
                DirectorArcOption(id="arc_b", title="旁支压近"),
                DirectorArcOption(id="arc_c", title="暗线回扣"),
            ],
        ),
    )
    store.save_model(
        store.selected_arc_path("demo"),
        SelectedArc(
            selected_option_id="arc_a",
            selected_at=now,
            arc_options_digest="digest",
        ),
    )
    previous_result = PipelineRunResult(
        session_name="demo",
        input_path=str(input_path),
        stage1_snapshot_path="stage1_snapshot.json",
        index_result=IndexingResult(source_path=str(input_path), chunk_count=1, character_count=1000),
        chapters=[
            ChapterRunResult(
                chapter_number=1,
                skeleton_path="chapter_1_skeleton.json",
                status="completed",
            )
        ],
    )
    store.save_model(store.run_manifest_path("demo"), previous_result)

    snapshot = ExtractionSnapshot(
        style_profile=StyleProfile(),
        story_state=StoryWorldState(title="红楼梦"),
    )
    context = PreparedStoryContext(
        index_result=IndexingResult(source_path=str(input_path), chunk_count=1, character_count=1000),
        snapshot=snapshot,
        snapshot_path=str(store.stage1_snapshot_path("demo")),
        source_text=input_path.read_text(encoding="utf-8"),
        stage1_usage=LLMUsageSummary(),
        world_model=WorldModel(),
        world_model_path=store.world_model_path("demo"),
        lorebook=LorebookBundle(),
        selected_references=[],
        arc_outline=ArcOutline(
            arc_id="arc_0002_0002",
            arc_theme="旧事浮现",
            arc_goal="让旧事浮出水面",
            chapters_span=[2, 2],
        ),
        expansion_budget=ExpansionBudget(),
    )
    skeleton = ChapterSkeleton(
        chapter_number=2,
        chapter_theme="旧事浮现",
        scenes=[
            SceneNode(
                scene_type="interior",
                participants=["宝玉"],
                scene_purpose="让旧事浮出水面",
            )
        ],
    )
    clean_gate = _TrackingCleanGate()
    challenge_builder = _TrackingBlindChallengeBuilder()
    blind_judge = _FailingBlindJudge()
    chapter_generator = _FakeChapterGenerator()
    quality_checker = _FakeQualityChecker()

    orchestrator = TaiJianOrchestrator.__new__(TaiJianOrchestrator)
    orchestrator.settings = settings
    orchestrator.session_store = store
    orchestrator.llm_service = _FakeUsageService()
    orchestrator.chapter_allocator = _FakeChapterAllocator()
    orchestrator.intervention = _FakeIntervention()
    orchestrator.lorebook_manager = _FakeLorebookManager()
    orchestrator.style_sampler = _FakeStyleSampler()
    orchestrator.chapter_generator = chapter_generator
    orchestrator.quality_checker = quality_checker
    orchestrator.revival_diagnosis_builder = RevivalDiagnosisBuilder()
    orchestrator.blind_challenge_builder = challenge_builder
    orchestrator.blind_judge = blind_judge

    async def prepare_story_context(**kwargs) -> PreparedStoryContext:
        return context

    async def prepare_skeleton(**kwargs):
        return skeleton, ConsistencyReport(passed=True)

    async def prepare_draft(**kwargs):
        draft_path = store.chapter_draft_path("demo", 2)
        store.save_text(draft_path, "草稿正文。")
        return "草稿正文。", draft_path

    async def finalize_output(**kwargs):
        return "初稿正文。", QualityReport(score=0.9, verdict="pass")

    orchestrator._prepare_story_context = prepare_story_context
    orchestrator._load_or_build_revival_workspace = lambda **kwargs: workspace
    orchestrator._clean_prose_gate_for_workspace = lambda workspace: clean_gate
    orchestrator._prepare_skeleton = prepare_skeleton
    orchestrator._prepare_draft = prepare_draft
    orchestrator._finalize_output = finalize_output

    result = await orchestrator.run_revival_generation(
        input_path=input_path,
        session_name="demo",
        start_chapter=2,
    )

    assert result.status == "failed"
    assert result.chapters[0].status == "failed_blind_judge"
    assert [call["issues"] for call in chapter_generator.revise_calls] == [["句法太现代"]]
    assert clean_gate.checked_texts == ["初稿正文。", "改后正文。"]
    assert challenge_builder.texts == ["初稿正文。", "改后正文。"]
    assert blind_judge.round_numbers == [1, 2]
    assert quality_checker.evaluated_texts == ["改后正文。"]
    assert store.chapter_revival_candidate_path("demo", 2).read_text(encoding="utf-8") == "改后正文。"
    assert store.blind_judge_report_path("demo").exists()
    manifest = store.load_model(store.run_manifest_path("demo"), PipelineRunResult)
    assert isinstance(manifest, PipelineRunResult)
    assert [chapter.chapter_number for chapter in manifest.chapters] == [1, 2]
    assert [chapter.status for chapter in manifest.chapters] == ["completed", "failed_blind_judge"]


def test_settings_candidate_counts_can_be_overridden() -> None:
    settings = AppSettings(
        tuning=RuntimeTuning(
            skeleton_candidate_count=2,
            draft_candidate_count=3,
            blind_judge_retry_limit=2,
            blind_judge_confidence_threshold=0.7,
        )
    )

    assert settings.tuning.skeleton_candidate_count == 2
    assert settings.tuning.draft_candidate_count == 3
    assert settings.tuning.blind_judge_retry_limit == 2
    assert settings.tuning.blind_judge_confidence_threshold == 0.7
