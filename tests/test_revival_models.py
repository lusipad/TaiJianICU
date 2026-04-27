from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from core.models.revival import (
    BlindChallenge,
    DirectorArcOption,
    DirectorArcOptions,
    SelectedArc,
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
    )
    challenge = BlindChallenge(excerpt_text="沈照站在雨里。", excerpt_char_count=7)

    assert work_skill.schema_version == "1.0"
    assert len(options.options) == 3
    assert selected.user_note == ""
    assert challenge.source_label_hidden is True


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
