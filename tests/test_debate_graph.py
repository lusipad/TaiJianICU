from core.models.skeleton import AgentProposal, ArbitrationDecision, ChapterSkeleton, SceneNode
from core.models.story_state import CharacterCard, StoryThread, StoryWorldState
from pipeline.stage2_plot.consistency_checker import ConsistencyReport
from pipeline.stage2_plot.debate_graph import DebateGraph


class FakeAgentService:
    async def load_context(self, **kwargs):
        return "主角刚刚得知真相。"

    async def build_proposals(self, **kwargs):
        return [
            AgentProposal(
                goal="试探敌意",
                action_proposal="主角先与盟友商议，再试探反派态度。",
                reasoning="符合谨慎型主角的推进方式。",
                risks=["节奏过慢"],
            )
        ]

    async def build_critiques(self, **kwargs):
        from core.models.skeleton import DebateCritique

        return [
            DebateCritique(
                stance="支持",
                critique="先试探再升级冲突更稳妥。",
                supports=["行动谨慎"],
                opposes=[],
            )
        ]

    async def arbitrate(self, **kwargs):
        return ArbitrationDecision(
            chapter_theme="暗流试探",
            winning_plan="先试探，后升级矛盾。",
            must_include_beats=["试探反派", "盟友分歧"],
            threads_to_advance=["T001"],
        )


class FakeSkeletonBuilder:
    def __init__(self):
        self.calls = 0

    async def build(self, **kwargs):
        self.calls += 1
        return ChapterSkeleton(
            chapter_number=kwargs["chapter_number"],
            chapter_theme="暗流试探",
            scenes=[
                SceneNode(scene_type="对话", participants=["主角"], scene_purpose="定调", estimated_word_count=500),
                SceneNode(scene_type="对话", participants=["主角", "盟友"], scene_purpose="分歧", estimated_word_count=500),
                SceneNode(scene_type="冲突", participants=["主角", "反派"], scene_purpose="试探", estimated_word_count=800),
            ],
            threads_to_advance=["T001"],
            threads_to_close=[],
            agent_consensus_log=kwargs["consensus_log"],
        )


class FlakyConsistencyChecker:
    retry_limit = 1

    def __init__(self):
        self.calls = 0

    def check(self, skeleton, focus_threads):
        self.calls += 1
        if self.calls == 1:
            return ConsistencyReport(passed=False, issues=["首轮要求重试"])
        return ConsistencyReport(passed=True, issues=[])


async def test_debate_graph_retries_and_returns_skeleton() -> None:
    builder = FakeSkeletonBuilder()
    checker = FlakyConsistencyChecker()
    graph = DebateGraph(FakeAgentService(), builder, checker)  # type: ignore[arg-type]

    skeleton, report = await graph.plan_chapter(
        session_name="demo",
        chapter_number=1,
        chapter_goal="推进旧仇主线",
        story_state=StoryWorldState(
            summary="主角与反派旧仇未解。",
            main_characters=[
                CharacterCard(
                    name="主角",
                    role="主视角",
                    personality_traits=["谨慎"],
                    core_goals=["复仇"],
                    speech_style="克制",
                    last_known_state="掌握了新线索",
                )
            ],
        ),
        focus_threads=[StoryThread(id="T001", description="旧仇", introduced_at=1, last_advanced=1)],
    )

    assert report.passed
    assert checker.calls == 2
    assert builder.calls == 2
    assert skeleton.chapter_theme == "暗流试探"
