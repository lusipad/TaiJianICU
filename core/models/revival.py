from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class WorkSkillEvidenceRef(_StrictModel):
    source: str
    note: str = ""
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)


class CharacterVoiceRule(_StrictModel):
    character_name: str
    voice_summary: str = ""
    diction_rules: list[str] = Field(default_factory=list)
    taboo_moves: list[str] = Field(default_factory=list)


class RevivalChapter(_StrictModel):
    chapter_number: int | None = Field(default=None, ge=1)
    title: str = ""
    text: str
    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)


class StyleMetrics(_StrictModel):
    chinese_char_count: int = Field(default=0, ge=0)
    avg_sentence_length: float = Field(default=0.0, ge=0.0)
    dialogue_ratio: float = Field(default=0.0, ge=0.0, le=1.0)
    function_word_density: dict[str, float] = Field(default_factory=dict)


class RevivalStyleBible(_StrictModel):
    schema_version: str = "1.0"
    generated_at: datetime
    work_title: str | None = None
    narrative_patterns: list[str] = Field(default_factory=list)
    style_metrics: StyleMetrics = Field(default_factory=StyleMetrics)
    forbidden_words: list[str] = Field(default_factory=list)
    character_voice_cards: list[CharacterVoiceRule] = Field(default_factory=list)


class RevivalWorkspaceArtifacts(_StrictModel):
    schema_version: str = "1.0"
    source_digest: str
    chapters: list[RevivalChapter] = Field(default_factory=list)
    style_bible: RevivalStyleBible
    forbidden_words: list[str] = Field(default_factory=list)


class WorkSkill(_StrictModel):
    schema_version: str = "1.0"
    source_digest: str
    generated_at: datetime
    work_title: str | None = None
    voice_rules: list[str] = Field(default_factory=list)
    rhythm_rules: list[str] = Field(default_factory=list)
    character_voice_map: list[CharacterVoiceRule] = Field(default_factory=list)
    world_rules: list[str] = Field(default_factory=list)
    open_threads: list[str] = Field(default_factory=list)
    forbidden_moves: list[str] = Field(default_factory=list)
    evidence_refs: list[WorkSkillEvidenceRef] = Field(default_factory=list)


class DirectorArcOption(_StrictModel):
    id: str
    title: str
    character_focus: list[str] = Field(default_factory=list)
    emotional_direction: str = ""
    must_happen: list[str] = Field(default_factory=list)
    must_not_break: list[str] = Field(default_factory=list)
    consequences: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)
    evidence_refs: list[WorkSkillEvidenceRef] = Field(default_factory=list)


class DirectorArcOptions(_StrictModel):
    schema_version: str = "1.0"
    generated_at: datetime
    options: list[DirectorArcOption] = Field(min_length=3, max_length=3)


class SelectedArc(_StrictModel):
    selected_option_id: str
    selected_at: datetime
    arc_options_digest: str
    user_note: str = ""
    locked_constraints: list[str] = Field(default_factory=list)


class CleanProseHit(_StrictModel):
    code: str
    label: str
    excerpt: str


class CleanProseGateResult(_StrictModel):
    status: Literal["pass", "fail"]
    chinese_char_count: int = 0
    hits: list[CleanProseHit] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "pass"


class RevivalDiagnosis(_StrictModel):
    status: Literal["pass", "fail", "warning"]
    gate_results: list[CleanProseGateResult] = Field(default_factory=list)
    contamination_hits: list[CleanProseHit] = Field(default_factory=list)
    voice_fit: float | None = Field(default=None, ge=0.0, le=1.0)
    plot_alignment: float | None = Field(default=None, ge=0.0, le=1.0)
    character_fit: float | None = Field(default=None, ge=0.0, le=1.0)
    retry_count: int = Field(default=0, ge=0)
    failure_reasons: list[str] = Field(default_factory=list)
    recommended_fix: str = ""


class BlindChallengeRating(_StrictModel):
    voice_match_score: int | None = Field(default=None, ge=1, le=5)
    rhythm_match_score: int | None = Field(default=None, ge=1, le=5)
    character_voice_score: int | None = Field(default=None, ge=1, le=5)
    notes: str = ""


class BlindChallengeExcerpt(_StrictModel):
    excerpt_id: str
    text: str
    excerpt_char_count: int = Field(ge=0)
    source_note: str = ""


class BlindChallenge(_StrictModel):
    excerpt_text: str
    excerpt_char_count: int = Field(ge=0)
    source_label_hidden: bool = True
    excerpts: list[BlindChallengeExcerpt] = Field(default_factory=list)
    generated_excerpt_id: str | None = None
    ratings: BlindChallengeRating | None = None
    rated_at: datetime | None = None
    notes: str = ""


class BlindJudgeDecision(_StrictModel):
    suspected_excerpt_id: str
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    reason: str = ""
    unlike_sentences: list[str] = Field(default_factory=list)
    rewrite_guidance: list[str] = Field(default_factory=list)


class BlindJudgeRound(_StrictModel):
    round_number: int = Field(ge=1)
    generated_excerpt_id: str | None = None
    decision: BlindJudgeDecision
    passed: bool
    failure_reasons: list[str] = Field(default_factory=list)


class BlindJudgeReport(_StrictModel):
    status: Literal["pass", "fail", "skipped"]
    confidence_threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    rounds: list[BlindJudgeRound] = Field(default_factory=list)

    @property
    def passed(self) -> bool:
        return self.status == "pass"
