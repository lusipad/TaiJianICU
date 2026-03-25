from __future__ import annotations

from pydantic import BaseModel, Field

from core.models.chapter_brief import ChapterBrief
from core.models.skeleton import ChapterSkeleton
from core.models.story_state import StoryThread
from pipeline.stage2_plot.consistency_checker import ConsistencyReport
from pipeline.stage3_generation.quality_checker import QualityReport


class SkeletonCandidate(BaseModel):
    skeleton: ChapterSkeleton
    consistency_report: ConsistencyReport
    candidate_number: int = 1
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class DraftCandidate(BaseModel):
    draft_text: str
    quality_report: QualityReport
    candidate_number: int = 1
    score: float = 0.0
    reasons: list[str] = Field(default_factory=list)


class CandidateRanker:
    def rank_skeletons(
        self,
        *,
        chapter_brief: ChapterBrief,
        focus_threads: list[StoryThread],
        candidates: list[SkeletonCandidate],
    ) -> list[SkeletonCandidate]:
        ranked: list[SkeletonCandidate] = []
        for candidate in candidates:
            score, reasons = self._score_skeleton(
                chapter_brief=chapter_brief,
                focus_threads=focus_threads,
                candidate=candidate,
            )
            ranked.append(candidate.model_copy(update={"score": score, "reasons": reasons}))
        return sorted(
            ranked,
            key=lambda item: (item.score, item.consistency_report.passed, -item.candidate_number),
            reverse=True,
        )

    def rank_drafts(
        self,
        *,
        chapter_brief: ChapterBrief,
        skeleton: ChapterSkeleton,
        candidates: list[DraftCandidate],
    ) -> list[DraftCandidate]:
        ranked: list[DraftCandidate] = []
        for candidate in candidates:
            score, reasons = self._score_draft(
                chapter_brief=chapter_brief,
                skeleton=skeleton,
                candidate=candidate,
            )
            ranked.append(candidate.model_copy(update={"score": score, "reasons": reasons}))
        return sorted(
            ranked,
            key=lambda item: (item.score, item.quality_report.score, -item.candidate_number),
            reverse=True,
        )

    def _score_skeleton(
        self,
        *,
        chapter_brief: ChapterBrief,
        focus_threads: list[StoryThread],
        candidate: SkeletonCandidate,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = 0.0
        if candidate.consistency_report.passed:
            score += 0.45
            reasons.append("一致性通过")
        else:
            score += 0.1
            reasons.append("一致性未通过")

        focus_ids = {item.id for item in focus_threads}
        advanced_ids = set(candidate.skeleton.threads_to_advance) | set(candidate.skeleton.threads_to_close)
        if focus_ids:
            coverage = len(focus_ids & advanced_ids) / len(focus_ids)
            score += coverage * 0.25
            reasons.append(f"重点伏笔覆盖 {coverage:.2f}")

        chapter_text = " ".join(
            [
                candidate.skeleton.chapter_theme,
                *[scene.scene_purpose for scene in candidate.skeleton.scenes],
            ]
        )
        must_hits = sum(1 for item in chapter_brief.must_happen if item and item[:6] in chapter_text)
        if chapter_brief.must_happen:
            coverage = must_hits / len(chapter_brief.must_happen)
            score += coverage * 0.2
            reasons.append(f"必须事件命中 {coverage:.2f}")

        if 3 <= len(candidate.skeleton.scenes) <= 6:
            score += 0.1
            reasons.append("场景数落在目标区间")

        return round(min(score, 1.0), 4), reasons

    def _score_draft(
        self,
        *,
        chapter_brief: ChapterBrief,
        skeleton: ChapterSkeleton,
        candidate: DraftCandidate,
    ) -> tuple[float, list[str]]:
        reasons: list[str] = []
        score = candidate.quality_report.score * 0.6
        reasons.append(f"质检分 {candidate.quality_report.score:.2f}")

        draft_text = candidate.draft_text
        participants = {
            participant
            for scene in skeleton.scenes
            for participant in scene.participants
            if participant.strip()
        }
        if participants:
            participant_hits = sum(1 for item in participants if item in draft_text)
            coverage = participant_hits / len(participants)
            score += coverage * 0.15
            reasons.append(f"角色覆盖 {coverage:.2f}")

        if chapter_brief.must_happen:
            must_hits = sum(1 for item in chapter_brief.must_happen if item[:6] in draft_text)
            coverage = must_hits / len(chapter_brief.must_happen)
            score += coverage * 0.15
            reasons.append(f"必须事件命中 {coverage:.2f}")

        length_score = min(len(draft_text) / 2500, 1.0)
        score += length_score * 0.1
        reasons.append(f"篇幅得分 {length_score:.2f}")

        return round(min(score, 1.0), 4), reasons
