from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.models.revival import (
    BlindChallenge,
    BlindChallengeExcerpt,
    BlindJudgeDecision,
    BlindJudgeReport,
    BlindJudgeRound,
    DirectorArcOption,
    DirectorArcOptions,
    DirectorIntentTranslation,
    RevivalChapter,
    RevivalStyleBible,
    RevivalTrustCheck,
    RevivalTrustReport,
    RevivalWorkspaceArtifacts,
    SelectedArc,
    StyleMetrics,
    WorkSkill,
)


def test_revival_artifacts_validate_expected_shape() -> None:
    now = datetime.now(timezone.utc)

    work_skill = WorkSkill(
        source_digest="abc123",
        generated_at=now,
        voice_rules=["短句压迫感"],
        rhythm_rules=["冲突后留悬念"],
    )
    options = DirectorArcOptions(
        generated_at=now,
        options=[
            DirectorArcOption(id="arc_a", title="压抑升温"),
            DirectorArcOption(id="arc_b", title="关系破冰"),
            DirectorArcOption(id="arc_c", title="反派暂胜"),
        ],
    )
    selected = SelectedArc(
        selected_option_id="arc_a",
        selected_at=now,
        arc_options_digest="digest",
        director_constraints=DirectorIntentTranslation(
            raw_intent="关系变化",
            internalized_actions=["旧事忽有新证"],
            scene_constraints=["不可直写解释"],
            forbidden_leaks=["关系变化"],
            status="generated",
        ),
    )
    trust_report = RevivalTrustReport(
        status="warning",
        summary="需要修订。",
        generated_at=now,
        chapter_number=80,
        checks=[
            RevivalTrustCheck(
                id="clean_prose",
                label="clean prose",
                status="warning",
                evidence=["命中现代词"],
                expected="无污染词",
                observed="命中 1 项",
                source="revival_diagnosis",
                recommended_action="重写该句",
            )
        ],
        recommended_actions=["重写该句"],
        revision_notes=["只输出修订后的正文。", "clean prose：重写该句"],
    )
    challenge = BlindChallenge(excerpt_text="沈照站在雨里。", excerpt_char_count=7)
    decision = BlindJudgeDecision(suspected_excerpt_id="A", confidence=0.8)
    judge_report = BlindJudgeReport(
        status="fail",
        rounds=[
            BlindJudgeRound(
                round_number=1,
                generated_excerpt_id="A",
                decision=decision,
                passed=False,
            )
        ],
    )
    chapter = RevivalChapter(
        chapter_number=80,
        title="旧案重启",
        text="沈照站在雨里。",
        start_char=0,
        end_char=7,
    )
    style_bible = RevivalStyleBible(
        generated_at=now,
        style_metrics=StyleMetrics(
            chinese_char_count=7,
            avg_sentence_length=7,
            dialogue_ratio=0,
            function_word_density={"的": 0.0},
        ),
        forbidden_words=["安全感"],
    )
    artifacts = RevivalWorkspaceArtifacts(
        source_digest="abc123",
        chapters=[chapter],
        style_bible=style_bible,
        forbidden_words=style_bible.forbidden_words,
    )

    assert work_skill.schema_version == "1.0"
    assert len(options.options) == 3
    assert selected.user_note == ""
    assert selected.director_constraints is not None
    assert trust_report.status == "warning"
    assert trust_report.checks[0].recommended_action == "重写该句"
    assert trust_report.revision_notes[1] == "clean prose：重写该句"
    assert challenge.source_label_hidden is True
    assert judge_report.rounds[0].decision.suspected_excerpt_id == "A"
    assert artifacts.chapters[0].chapter_number == 80
    assert artifacts.style_bible.forbidden_words == ["安全感"]


def test_director_arc_options_require_exactly_three_options() -> None:
    now = datetime.now(timezone.utc)

    with pytest.raises(ValidationError):
        DirectorArcOptions(
            generated_at=now,
            options=[
                DirectorArcOption(id="arc_a", title="压抑升温"),
                DirectorArcOption(id="arc_b", title="关系破冰"),
            ],
        )


def test_revival_models_reject_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        WorkSkill(
            source_digest="abc123",
            generated_at=datetime.now(timezone.utc),
            unexpected="should fail",
        )

    with pytest.raises(ValidationError):
        DirectorIntentTranslation(raw_intent="推进人物弧光", unexpected="should fail")


def test_blind_challenge_excerpt_rejects_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        BlindChallengeExcerpt(
            excerpt_id="A",
            text="沈照站在雨里。",
            excerpt_char_count=7,
            source_note="",
            answer="generated",
        )
