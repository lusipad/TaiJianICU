from __future__ import annotations

from config.settings import AppSettings
from core.models.arc_outline import ArcOutline
from core.models.lorebook import LorebookBundle, LorebookEntry
from core.models.story_state import CharacterCard, StoryThread, StoryWorldState
from core.models.style_profile import ExtractionSnapshot, StyleProfile
from core.models.world_model import WorldModel
from core.models.revival import BlindJudgeDecision
from pipeline.revival import (
    BlindChallengeBuilder,
    BlindJudge,
    ChapterSplitter,
    CleanProseGate,
    RevivalArcPlanner,
    RevivalDiagnosisBuilder,
    RevivalWorkspaceBuilder,
    SourceVoiceGate,
    StyleBibleBuilder,
    WorkSkillBuilder,
    digest_payload,
)


class _FakeBlindJudgeLLM:
    def __init__(self, decision: BlindJudgeDecision):
        self.decision = decision
        self.messages = []

    async def complete_structured(self, **kwargs):
        self.messages = kwargs["messages"]
        return self.decision


def _snapshot() -> ExtractionSnapshot:
    return ExtractionSnapshot(
        style_profile=StyleProfile(
            narrative_person="第三人称",
            pacing="慢热压迫",
            tone_keywords=["冷峻", "悬疑"],
            sentence_rhythm="短句后接长句",
            dialogue_style="克制",
            signature_devices=["章末留钩子"],
            taboo_patterns=["不要突然揭底"],
            summary="雨夜悬疑感强",
        ),
        story_state=StoryWorldState(
            title="雨夜追魂",
            summary="旧案重启",
            world_rules=["义庄旧案不能直接公开"],
            main_characters=[
                CharacterCard(
                    name="沈照",
                    personality_traits=["谨慎"],
                    speech_style="话少，句子短",
                )
            ],
            active_conflicts=["尾随者逼近"],
            unresolved_threads=[
                StoryThread(id="T001", description="黑玉去向", introduced_at=1)
            ],
        ),
    )


def test_work_skill_builder_reuses_snapshot_world_and_lorebook() -> None:
    work_skill = WorkSkillBuilder().build(
        snapshot=_snapshot(),
        world_model=WorldModel(power_system_rules=["义庄旧案不能直接公开", "黑玉规则稳定"]),
        lorebook=LorebookBundle(
            entries=[
                LorebookEntry(
                    entry_id="L001",
                    title="黑玉",
                    content="黑玉不能突然完整出现。",
                )
            ]
        ),
        source_digest="abc123",
    )

    assert work_skill.work_title == "雨夜追魂"
    assert "叙事人称：第三人称" in work_skill.voice_rules
    assert work_skill.character_voice_map[0].character_name == "沈照"
    assert work_skill.world_rules == ["义庄旧案不能直接公开", "黑玉规则稳定"]
    assert work_skill.open_threads == ["T001: 黑玉去向"]
    assert work_skill.evidence_refs[0].source == "L001"


def test_revival_arc_planner_returns_three_stable_options() -> None:
    snapshot = _snapshot()
    work_skill = WorkSkillBuilder().build(
        snapshot=snapshot,
        world_model=WorldModel(),
        lorebook=LorebookBundle(),
        source_digest="abc123",
    )

    options = RevivalArcPlanner().plan_options(
        work_skill=work_skill,
        snapshot=snapshot,
        world_model=WorldModel(),
        arc_outline=ArcOutline(
            arc_id="arc_0001_0001",
            arc_theme="旧案发酵",
            arc_goal="逼近黑玉真相",
            chapters_span=[1, 1],
        ),
    )

    assert [item.id for item in options.options] == [
        "arc_conservative",
        "arc_emotional",
        "arc_pressure_turn",
    ]
    assert digest_payload(options.model_dump(mode="json"))


def test_revival_diagnosis_and_blind_challenge_builders() -> None:
    gate_result = CleanProseGate().check("沈照站在义庄门口。")
    diagnosis = RevivalDiagnosisBuilder().build(
        gate_result=gate_result,
        quality_score=0.8,
        retry_count=0,
    )
    challenge = BlindChallengeBuilder().build("沈照站在义庄门口。" * 200, target_chars=1000)

    assert diagnosis.status == "pass"
    assert diagnosis.voice_fit == 0.8
    assert challenge.excerpt_char_count == 1000
    assert challenge.source_label_hidden is True


def test_chapter_splitter_detects_hui_headings() -> None:
    text = (
        "第八十回 美香菱屈受贪夫棒 王道士胡诌妒妇方\n"
        "却说香菱听了，只低头不语。\n"
        "第八十一回 占旺相四美钓游鱼 奉严词两番入家塾\n"
        "话说宝玉病后初起。"
    )

    chapters = ChapterSplitter().split(text)

    assert [chapter.chapter_number for chapter in chapters] == [80, 81]
    assert chapters[0].title == "美香菱屈受贪夫棒 王道士胡诌妒妇方"
    assert "香菱" in chapters[0].text
    assert chapters[1].start_char > chapters[0].start_char


def test_chapter_splitter_falls_back_to_single_chapter() -> None:
    chapters = ChapterSplitter().split("沈照站在雨里。")

    assert len(chapters) == 1
    assert chapters[0].chapter_number == 1
    assert chapters[0].title == "全文"


def test_chapter_splitter_dedupes_adjacent_duplicate_headings() -> None:
    text = (
        "第四十五回 金蘭契互剖金蘭語\n"
        "第四十五回 金蘭契互剖金蘭語\n"
        "話說黛玉聽了，低頭不語。\n"
        "第四十六回 尷尬人難免尷尬事\n"
        "且說鴛鴦心中不願。"
    )

    chapters = ChapterSplitter().split(text)

    assert [chapter.chapter_number for chapter in chapters] == [45, 46]
    assert "黛玉" in chapters[0].text


def test_style_bible_builder_measures_voice_surface() -> None:
    text = "且说宝玉病后初起。谁知黛玉听了，冷笑道：“你又来哄我。”"

    style_bible = StyleBibleBuilder().build(text, work_title="红楼梦")

    assert style_bible.work_title == "红楼梦"
    assert "且说" in style_bible.narrative_patterns
    assert "安全感" in style_bible.forbidden_words
    assert style_bible.style_metrics.chinese_char_count > 0
    assert style_bible.style_metrics.avg_sentence_length > 0
    assert style_bible.style_metrics.dialogue_ratio > 0
    assert [card.character_name for card in style_bible.character_voice_cards] == ["宝玉", "黛玉"]


def test_source_voice_gate_flags_short_modern_candidate_against_chapter_baseline() -> None:
    source = "\n\n".join(
        [
            f"第{number}回 旧事\n话说宝玉进来，笑道：“你且听我说。”"
            + "众人一面说笑，一面看那阶前花影。" * 80
            for number in ("一", "二", "三")
        ]
    )
    gate = SourceVoiceGate.from_source_text(source)

    result = gate.check("本章推进宝玉的人物弧光。众人沉默。")

    assert not result.passed
    assert {"source_baseline_too_short", "chapter_meta"} <= {hit.code for hit in result.hits}


def test_revival_workspace_builder_creates_serializable_artifacts() -> None:
    text = "第八十回 旧事\n且说宝玉病后初起。\n第八十一回 新章\n话说黛玉低头不语。"

    artifacts = RevivalWorkspaceBuilder().build(text, work_title="红楼梦")

    assert artifacts.source_digest
    assert len(artifacts.chapters) == 2
    assert artifacts.style_bible.work_title == "红楼梦"
    assert artifacts.model_dump(mode="json")["chapters"][0]["chapter_number"] == 80


def test_blind_challenge_builder_mixes_generated_and_canon_excerpts() -> None:
    source = (
        "第八十回 旧事\n" + "且说宝玉病后初起。" * 20 + "\n"
        "第八十一回 新章\n" + "谁知黛玉听了冷笑。" * 20 + "\n"
        "第八十二回 又章\n" + "原来袭人早在房中。" * 20
    )
    chapters = ChapterSplitter().split(source)

    challenge = BlindChallengeBuilder().build(
        "生成正文。" * 20,
        target_chars=20,
        source_chapters=chapters,
    )

    assert len(challenge.excerpts) == 4
    assert {item.excerpt_id for item in challenge.excerpts} == {"A", "B", "C", "D"}
    assert challenge.generated_excerpt_id in {"A", "B", "C", "D"}
    assert all(item.source_note == "" for item in challenge.excerpts)


def test_blind_judge_marks_caught_generated_as_failure() -> None:
    challenge = BlindChallengeBuilder().build(
        "生成正文。" * 20,
        target_chars=20,
        source_text="原文片段。" * 80,
    )
    decision = BlindJudgeDecision(
        suspected_excerpt_id=challenge.generated_excerpt_id or "",
        confidence=0.9,
        reason="句法太现代",
        unlike_sentences=["生成正文"],
        rewrite_guidance=["减少现代短句"],
    )

    round_result = BlindJudge.evaluate_decision(
        challenge=challenge,
        decision=decision,
        round_number=1,
        confidence_threshold=0.6,
    )
    report = BlindJudge.report(rounds=[round_result], confidence_threshold=0.6)

    assert round_result.passed is False
    assert "句法太现代" in round_result.failure_reasons
    assert report.status == "fail"


def test_blind_judge_passes_low_confidence_identification() -> None:
    challenge = BlindChallengeBuilder().build(
        "生成正文。" * 20,
        target_chars=20,
        source_text="原文片段。" * 80,
    )
    decision = BlindJudgeDecision(
        suspected_excerpt_id=challenge.generated_excerpt_id or "",
        confidence=0.3,
    )

    round_result = BlindJudge.evaluate_decision(
        challenge=challenge,
        decision=decision,
        round_number=1,
        confidence_threshold=0.6,
    )

    assert round_result.passed is True
    assert round_result.failure_reasons == []


async def test_blind_judge_calls_llm_with_redacted_excerpts() -> None:
    challenge = BlindChallengeBuilder().build(
        "生成正文。" * 20,
        target_chars=20,
        source_text="原文片段。" * 80,
    )
    fake_llm = _FakeBlindJudgeLLM(
        BlindJudgeDecision(
            suspected_excerpt_id=challenge.generated_excerpt_id or "",
            confidence=0.95,
        )
    )
    judge = BlindJudge(AppSettings(), fake_llm)  # type: ignore[arg-type]
    style_bible = StyleBibleBuilder().build("且说宝玉病后初起。", work_title="红楼梦")

    result = await judge.judge(
        challenge=challenge,
        style_bible=style_bible,
        round_number=1,
    )

    assert result.passed is False
    assert fake_llm.messages
    prompt = fake_llm.messages[0]["content"]
    assert "source_note" not in prompt
    assert "generated_excerpt_id" not in prompt
