from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from core.models.revival import BlindChallenge, DirectorArcOptions, RevivalDiagnosis, SelectedArc, WorkSkill
from core.models.story_state import StoryThread


RunStatus = Literal[
    "queued",
    "running",
    "analyzing",
    "awaiting_arc_selection",
    "generating",
    "completed",
    "completed_with_warnings",
    "failed",
]


class WebRunRequest(BaseModel):
    session_name: str | None = None
    chapters: int = Field(default=1, ge=1, le=20)
    start_chapter: int = Field(default=1, ge=1, le=9999)
    goal_hint: str | None = None
    planning_mode: Literal["strict", "balanced", "expansive"] = "balanced"
    new_character_budget: int | None = Field(default=None, ge=0, le=5)
    new_location_budget: int | None = Field(default=None, ge=0, le=5)
    new_faction_budget: int | None = Field(default=None, ge=0, le=5)
    skeleton_candidates: int | None = Field(default=None, ge=1, le=5)
    draft_candidates: int | None = Field(default=None, ge=1, le=5)
    style_model: str | None = None
    plot_model: str | None = None
    draft_model: str | None = None
    quality_model: str | None = None
    lightrag_model_name: str | None = None
    use_existing_index: bool = False
    overwrite: bool = False


class WebRuntimeApiOverride(BaseModel):
    api_base_url: str | None = None
    api_key: str | None = None


class WebRunProgress(BaseModel):
    total_steps: int = 0
    completed_steps: int = 0
    message: str = "等待开始"

    @computed_field
    @property
    def percent(self) -> float:
        if self.total_steps <= 0:
            return 0.0
        return round(min(100.0, self.completed_steps / self.total_steps * 100.0), 2)

    @computed_field
    @property
    def completed_label(self) -> str:
        return f"{self.completed_steps}/{self.total_steps}"


class WebRunSummary(BaseModel):
    id: str
    status: RunStatus
    created_at: datetime
    updated_at: datetime
    session_name: str
    input_filename: str
    request: WebRunRequest
    progress: WebRunProgress
    error_message: str | None = None


class WebRunMetrics(BaseModel):
    total_calls: int = 0
    total_tokens: int = 0
    total_cost_usd: float = 0.0
    chapter_count: int = 0
    completed_chapters: int = 0
    latest_chapter_number: int | None = None
    latest_chapter_status: str | None = None
    latest_elapsed_seconds: float | None = None
    latest_quality_score: float | None = None
    latest_quality_verdict: str | None = None
    consistency_passed: bool | None = None


class WebRunArtifactPaths(BaseModel):
    manifest: str | None = None
    stage1_snapshot: str | None = None
    world_model: str | None = None
    lorebook: str | None = None
    selected_references: str | None = None
    work_skill: str | None = None
    arc_options: str | None = None
    selected_arc: str | None = None
    revival_diagnosis: str | None = None
    blind_challenge: str | None = None
    latest_skeleton: str | None = None
    latest_chapter_brief: str | None = None
    latest_chapter_evaluation: str | None = None
    latest_draft: str | None = None
    latest_output: str | None = None
    story_graph: str | None = None


class WebChapterSummary(BaseModel):
    chapter_number: int
    status: str
    chapter_goal: str | None = None
    output_path: str | None = None
    quality_verdict: str | None = None
    quality_score: float | None = None
    consistency_passed: bool | None = None
    elapsed_seconds: float = 0.0


class WebRunDetail(WebRunSummary):
    log_messages: list[str] = Field(default_factory=list)
    input_path: str | None = None
    manifest_path: str | None = None
    stage1_snapshot_path: str | None = None
    output_paths: list[str] = Field(default_factory=list)
    style_profile: dict | None = None
    story_state: dict | None = None
    world_model: dict | None = None
    lorebook: dict | None = None
    work_skill: WorkSkill | None = None
    arc_options: DirectorArcOptions | None = None
    arc_options_digest: str | None = None
    selected_arc: SelectedArc | None = None
    revival_diagnosis: RevivalDiagnosis | None = None
    blind_challenge: BlindChallenge | None = None
    selected_references: list[dict] = Field(default_factory=list)
    arc_outlines: list[dict] = Field(default_factory=list)
    latest_chapter_brief: dict | None = None
    latest_chapter_evaluation: dict | None = None
    latest_skeleton_candidate_paths: list[str] = Field(default_factory=list)
    latest_draft_candidate_paths: list[str] = Field(default_factory=list)
    latest_source_preview_label: str | None = None
    latest_source_preview: str | None = None
    latest_output_preview: str | None = None
    latest_quality_report: dict | None = None
    latest_consistency_report: dict | None = None
    latest_chapter_goal: str | None = None
    unresolved_threads: list[StoryThread] = Field(default_factory=list)
    artifact_paths: WebRunArtifactPaths = Field(default_factory=WebRunArtifactPaths)
    metrics: WebRunMetrics = Field(default_factory=WebRunMetrics)
    chapter_summaries: list[WebChapterSummary] = Field(default_factory=list)


class WebRunSourceText(BaseModel):
    input_filename: str
    text_content: str
    character_count: int = 0


class WebArcSelectionRequest(BaseModel):
    selected_option_id: str
    arc_options_digest: str | None = None
    user_note: str = ""


class WebBlindChallengeRatingRequest(BaseModel):
    voice_match_score: int | None = Field(default=None, ge=1, le=5)
    rhythm_match_score: int | None = Field(default=None, ge=1, le=5)
    character_voice_score: int | None = Field(default=None, ge=1, le=5)
    notes: str = ""


class ApiErrorResponse(BaseModel):
    title: str
    status: int
    detail: str


class WebRuntimeConfig(BaseModel):
    style_model: str
    plot_model: str
    draft_model: str
    quality_model: str
    lightrag_model_name: str
    api_base_url: str | None = None
    model_options: list[str] = Field(default_factory=list)


class WebExampleSummary(BaseModel):
    id: str
    title: str
    description: str
    input_filename: str
    recommended_goal_hint: str | None = None
    source_excerpt: str | None = None
    usage_hint: str | None = None
    trial_limit_note: str | None = None


class WebExampleDetail(WebExampleSummary):
    text_content: str


class WebPublicShowcase(BaseModel):
    title: str
    source_label: str
    source_excerpt: str
    output_label: str
    output_excerpt: str
    chapter_goal: str | None = None
    evaluation_summary: str | None = None
    continuity_score: float | None = None
    character_score: float | None = None
    world_consistency_score: float | None = None
    novelty_score: float | None = None
    arc_progress_score: float | None = None


class WebBenchmarkSummary(BaseModel):
    dataset_name: str
    case_name: str
    target_chapter_number: int
    prefix_chapter_count: int
    winner: str
    confidence: float
    report_json_path: str
    report_markdown_path: str


class WebBenchmarkDetail(WebBenchmarkSummary):
    system_output_path: str
    baseline_output_path: str
    reference_path: str
    pairwise_reasoning: list[str] = Field(default_factory=list)
    system_score: float = 0.0
    baseline_score: float = 0.0
    system_summary: str = ""
    baseline_summary: str = ""
    system_strengths: list[str] = Field(default_factory=list)
    baseline_strengths: list[str] = Field(default_factory=list)
    system_weaknesses: list[str] = Field(default_factory=list)
    baseline_weaknesses: list[str] = Field(default_factory=list)
    system_elapsed_seconds: float = 0.0
    baseline_elapsed_seconds: float = 0.0
    total_cost_usd: float = 0.0
    total_tokens: int = 0
