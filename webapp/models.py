from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, computed_field

from core.models.story_state import StoryThread


RunStatus = Literal["queued", "running", "completed", "failed"]


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
    use_existing_index: bool = False
    overwrite: bool = False


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
    selected_references: list[dict] = Field(default_factory=list)
    arc_outlines: list[dict] = Field(default_factory=list)
    latest_chapter_brief: dict | None = None
    latest_chapter_evaluation: dict | None = None
    latest_skeleton_candidate_paths: list[str] = Field(default_factory=list)
    latest_draft_candidate_paths: list[str] = Field(default_factory=list)
    latest_output_preview: str | None = None
    latest_quality_report: dict | None = None
    latest_consistency_report: dict | None = None
    latest_chapter_goal: str | None = None
    unresolved_threads: list[StoryThread] = Field(default_factory=list)
    artifact_paths: WebRunArtifactPaths = Field(default_factory=WebRunArtifactPaths)
    metrics: WebRunMetrics = Field(default_factory=WebRunMetrics)
    chapter_summaries: list[WebChapterSummary] = Field(default_factory=list)


class ApiErrorResponse(BaseModel):
    title: str
    status: int
    detail: str


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
