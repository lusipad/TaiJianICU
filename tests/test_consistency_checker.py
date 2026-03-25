from core.models.skeleton import ChapterSkeleton, SceneNode
from core.models.story_state import StoryThread
from pipeline.stage2_plot.consistency_checker import ConsistencyChecker


def test_consistency_checker_flags_missing_thread_progress() -> None:
    checker = ConsistencyChecker()
    skeleton = ChapterSkeleton(
        chapter_number=1,
        chapter_theme="试探",
        scenes=[
            SceneNode(scene_type="对话", participants=["主角"], scene_purpose="铺垫", estimated_word_count=500),
            SceneNode(scene_type="叙述", participants=["主角"], scene_purpose="推进", estimated_word_count=500),
            SceneNode(scene_type="战斗", participants=["主角", "反派"], scene_purpose="冲突", estimated_word_count=700),
        ],
        threads_to_advance=[],
        threads_to_close=[],
    )

    report = checker.check(
        skeleton,
        [StoryThread(id="T001", description="旧仇", introduced_at=1, last_advanced=1)],
    )

    assert not report.passed
    assert "指定伏笔" in report.issues[0]


def test_consistency_checker_passes_when_thread_is_touched() -> None:
    checker = ConsistencyChecker()
    skeleton = ChapterSkeleton(
        chapter_number=1,
        chapter_theme="试探",
        scenes=[
            SceneNode(scene_type="对话", participants=["主角"], scene_purpose="铺垫", estimated_word_count=500),
            SceneNode(scene_type="叙述", participants=["主角"], scene_purpose="推进", estimated_word_count=500),
            SceneNode(scene_type="战斗", participants=["主角", "反派"], scene_purpose="冲突", estimated_word_count=700),
        ],
        threads_to_advance=["T001"],
        threads_to_close=[],
    )

    report = checker.check(
        skeleton,
        [StoryThread(id="T001", description="旧仇", introduced_at=1, last_advanced=1)],
    )

    assert report.passed
