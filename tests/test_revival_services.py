from __future__ import annotations

from core.models.arc_outline import ArcOutline
from core.models.lorebook import LorebookBundle, LorebookEntry
from core.models.story_state import CharacterCard, StoryThread, StoryWorldState
from core.models.style_profile import ExtractionSnapshot, StyleProfile
from core.models.world_model import WorldModel
from pipeline.revival import (
    BlindChallengeBuilder,
    CleanProseGate,
    RevivalArcPlanner,
    RevivalDiagnosisBuilder,
    WorkSkillBuilder,
    digest_payload,
)


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
        world_model=WorldModel(power_system_rules=["黑玉规则稳定"]),
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
