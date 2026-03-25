from __future__ import annotations

from core.models.chapter_brief import ChapterBrief
from core.models.evaluation import ChapterEvaluation, EvaluationFlag, EvaluationScore
from core.models.skeleton import ChapterSkeleton
from core.models.world_model import WorldModel
from pipeline.stage2_plot.consistency_checker import ConsistencyReport
from pipeline.stage3_generation.quality_checker import QualityReport


class ReflectionUpdater:
    def evaluate_chapter(
        self,
        *,
        chapter_number: int,
        chapter_brief: ChapterBrief,
        world_model: WorldModel,
        skeleton: ChapterSkeleton,
        consistency_report: ConsistencyReport,
        quality_report: QualityReport,
        final_text: str,
    ) -> ChapterEvaluation:
        continuity_score = self._clamp(quality_report.score)
        character_score = self._character_score(world_model, skeleton, final_text)
        world_consistency_score = 0.9 if consistency_report.passed else 0.45
        novelty_score = self._novelty_score(chapter_brief, skeleton)
        arc_progress_score = self._arc_progress_score(
            chapter_brief,
            skeleton,
            consistency_report,
        )

        flags: list[EvaluationFlag] = []
        if quality_report.verdict != "pass":
            flags.append(
                EvaluationFlag(
                    code="LOW_QUALITY",
                    message="正文质量检查未通过，需要继续修订。",
                    severity="error",
                )
            )
        if not consistency_report.passed:
            flags.append(
                EvaluationFlag(
                    code="CONSISTENCY_RISK",
                    message="章节骨架与重点伏笔存在一致性风险。",
                    severity="error",
                )
            )
        if novelty_score < 0.55:
            flags.append(
                EvaluationFlag(
                    code="LOW_NOVELTY",
                    message="本章扩张或新意偏弱，推进感不足。",
                )
            )
        if arc_progress_score < 0.55:
            flags.append(
                EvaluationFlag(
                    code="LOW_ARC_PROGRESS",
                    message="本章对 arc 目标的推进力度不足。",
                )
            )

        if flags:
            summary = (
                f"第{chapter_number}章已执行，但存在问题："
                + "；".join(flag.message for flag in flags[:3])
            )
        else:
            summary = f"第{chapter_number}章围绕“{chapter_brief.chapter_goal}”完成执行，推进稳定。"

        return ChapterEvaluation(
            chapter_number=chapter_number,
            score=EvaluationScore(
                continuity_score=continuity_score,
                character_score=character_score,
                world_consistency_score=self._clamp(world_consistency_score),
                novelty_score=novelty_score,
                arc_progress_score=arc_progress_score,
            ),
            flags=flags,
            summary=summary,
            should_retry=any(flag.severity == "error" for flag in flags),
        )

    @staticmethod
    def _clamp(value: float) -> float:
        return round(max(0.0, min(1.0, value)), 3)

    def _character_score(
        self,
        world_model: WorldModel,
        skeleton: ChapterSkeleton,
        final_text: str,
    ) -> float:
        expected_names = {
            character.character_name
            for character in world_model.main_characters[:4]
            if character.character_name.strip()
        }
        expected_names.update(
            participant.strip()
            for scene in skeleton.scenes
            for participant in scene.participants
            if participant.strip()
        )
        if not expected_names:
            return 0.7
        hits = sum(1 for name in expected_names if name in final_text)
        return self._clamp(0.35 + 0.65 * (hits / len(expected_names)))

    def _novelty_score(
        self,
        chapter_brief: ChapterBrief,
        skeleton: ChapterSkeleton,
    ) -> float:
        score = 0.35
        if any(
            (
                chapter_brief.allowed_expansion.new_character,
                chapter_brief.allowed_expansion.new_location,
                chapter_brief.allowed_expansion.new_faction,
                chapter_brief.allowed_expansion.new_mystery,
            )
        ):
            score += 0.2
        if chapter_brief.may_introduce:
            score += 0.15
        if len(skeleton.scenes) >= 4:
            score += 0.15
        if skeleton.threads_to_advance:
            score += 0.1
        return self._clamp(score)

    def _arc_progress_score(
        self,
        chapter_brief: ChapterBrief,
        skeleton: ChapterSkeleton,
        consistency_report: ConsistencyReport,
    ) -> float:
        score = 0.3
        if chapter_brief.must_happen:
            score += 0.2
        if skeleton.threads_to_advance:
            score += 0.2
        if skeleton.threads_to_close:
            score += 0.1
        if consistency_report.passed:
            score += 0.15
        if chapter_brief.constraints:
            score += 0.1
        return self._clamp(score)
