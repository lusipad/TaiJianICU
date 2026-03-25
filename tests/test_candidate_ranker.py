from core.models.chapter_brief import ChapterBrief
from core.models.skeleton import ChapterSkeleton, SceneNode
from core.models.story_state import StoryThread
from core.services.reflection import CandidateRanker, DraftCandidate, SkeletonCandidate
from pipeline.stage2_plot.consistency_checker import ConsistencyReport
from pipeline.stage3_generation.quality_checker import QualityReport


def test_candidate_ranker_prefers_consistent_skeleton() -> None:
    ranker = CandidateRanker()
    ranked = ranker.rank_skeletons(
        chapter_brief=ChapterBrief(
            chapter_number=1,
            chapter_goal="推进旧案",
            must_happen=["主角拿到线索"],
        ),
        focus_threads=[StoryThread(id="T001", description="旧案线索")],
        candidates=[
            SkeletonCandidate(
                candidate_number=1,
                skeleton=ChapterSkeleton(
                    chapter_number=1,
                    chapter_theme="旧案推进",
                    scenes=[
                        SceneNode(
                            scene_type="调查",
                            participants=["主角"],
                            scene_purpose="主角拿到线索",
                            estimated_word_count=500,
                        )
                    ],
                    threads_to_advance=["T001"],
                ),
                consistency_report=ConsistencyReport(passed=True, issues=[]),
            ),
            SkeletonCandidate(
                candidate_number=2,
                skeleton=ChapterSkeleton(
                    chapter_number=1,
                    chapter_theme="闲聊",
                    scenes=[
                        SceneNode(
                            scene_type="对白",
                            participants=["配角"],
                            scene_purpose="闲谈",
                            estimated_word_count=500,
                        )
                    ],
                    threads_to_advance=[],
                ),
                consistency_report=ConsistencyReport(passed=False, issues=["未推进伏笔"]),
            ),
        ],
    )

    assert ranked[0].candidate_number == 1
    assert ranked[0].score > ranked[1].score


def test_candidate_ranker_prefers_higher_quality_draft() -> None:
    ranker = CandidateRanker()
    skeleton = ChapterSkeleton(
        chapter_number=1,
        chapter_theme="旧案推进",
        scenes=[
            SceneNode(
                scene_type="调查",
                participants=["沈照"],
                scene_purpose="主角拿到线索",
                estimated_word_count=500,
            )
        ],
        threads_to_advance=["T001"],
    )

    ranked = ranker.rank_drafts(
        chapter_brief=ChapterBrief(
            chapter_number=1,
            chapter_goal="推进旧案",
            must_happen=["主角拿到线索"],
        ),
        skeleton=skeleton,
        candidates=[
            DraftCandidate(
                candidate_number=1,
                draft_text="沈照终于拿到线索，心头一沉，旧案彻底被翻开。" * 80,
                quality_report=QualityReport(score=0.9, verdict="pass"),
            ),
            DraftCandidate(
                candidate_number=2,
                draft_text="天气不错。",
                quality_report=QualityReport(score=0.3, verdict="revise"),
            ),
        ],
    )

    assert ranked[0].candidate_number == 1
    assert ranked[0].score > ranked[1].score
