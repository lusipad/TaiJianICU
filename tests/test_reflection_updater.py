from core.models.chapter_brief import ChapterBrief, ChapterConstraint
from core.models.story_state import StoryThread
from core.models.world_model import CharacterArc, WorldModel
from core.models.skeleton import ChapterSkeleton, SceneNode
from core.services.reflection import ReflectionUpdater
from pipeline.stage2_plot.consistency_checker import ConsistencyReport
from pipeline.stage3_generation.quality_checker import QualityReport


def test_reflection_updater_builds_retry_evaluation() -> None:
    evaluation = ReflectionUpdater().evaluate_chapter(
        chapter_number=12,
        chapter_brief=ChapterBrief(
            chapter_number=12,
            chapter_goal="让旧案升级",
            must_happen=["主角拿到线索"],
            constraints=[ChapterConstraint(label="arc", content="推进 arc")],
        ),
        world_model=WorldModel(
            main_characters=[CharacterArc(character_name="沈照")],
            active_threads=[StoryThread(id="T001", description="黑玉去向")],
        ),
        skeleton=ChapterSkeleton(
            chapter_number=12,
            chapter_theme="旧案升级",
            scenes=[
                SceneNode(
                    scene_type="调查",
                    participants=["沈照"],
                    scene_purpose="拿到线索",
                    estimated_word_count=600,
                )
            ],
            threads_to_advance=[],
        ),
        consistency_report=ConsistencyReport(passed=False, issues=["伏笔未推进"]),
        quality_report=QualityReport(score=0.4, verdict="revise", issues=["过短"]),
        final_text="沈照站在雨里。",
    )

    assert evaluation.should_retry is True
    assert any(flag.code == "LOW_QUALITY" for flag in evaluation.flags)
    assert any(flag.code == "CONSISTENCY_RISK" for flag in evaluation.flags)
    assert evaluation.score.world_consistency_score < 0.5
