from __future__ import annotations

from core.models.skeleton import ChapterSkeleton, SceneNode
from core.models.style_profile import StyleProfile
from pipeline.stage3_generation.style_sampler import StyleSampler


class _FailingRagStore:
    async def sample_passages(self, session_name: str, query: str) -> list[str]:
        raise AssertionError("source-backed style sampling must not query generated session RAG")


async def test_style_sampler_uses_source_text_before_session_rag() -> None:
    source_text = (
        "第一回 起首\n话说宝玉初入园中，只见花影重重。\n"
        "第二回 承接\n且说黛玉听了，冷笑道：“你又来哄我。”\n"
        "第三回 风起\n原来袭人早在房中，见他神色不定，便不言语。"
    )
    sampler = StyleSampler(_FailingRagStore())  # type: ignore[arg-type]
    skeleton = ChapterSkeleton(
        chapter_number=4,
        chapter_theme="风起",
        scenes=[
            SceneNode(
                scene_type="interior",
                participants=["宝玉"],
                scene_purpose="旧事重提",
            )
        ],
    )

    samples = await sampler.sample(
        "demo",
        skeleton,
        StyleProfile(tone_keywords=["风起"]),
        source_text=source_text,
    )

    assert samples
    assert all("AI" not in sample for sample in samples)
