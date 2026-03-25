from __future__ import annotations

from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from core.models.chapter_brief import ChapterBrief
from core.models.lorebook import LorebookBundle
from core.models.skeleton import AgentConsensusLog, ArbitrationDecision, ChapterSkeleton
from core.models.story_state import StoryThread, StoryWorldState
from core.models.world_model import WorldModel
from pipeline.stage2_plot.agent_nodes import AgentNodeService
from pipeline.stage2_plot.consistency_checker import ConsistencyChecker, ConsistencyReport
from pipeline.stage2_plot.skeleton_builder import SkeletonBuilder


class DebateState(TypedDict, total=False):
    session_name: str
    chapter_number: int
    chapter_goal: str
    story_state: StoryWorldState
    world_model: WorldModel
    chapter_brief: ChapterBrief
    lorebook_context: LorebookBundle
    focus_threads: list[StoryThread]
    recalled_context: str
    proposals: list[BaseModel]
    critiques: list[BaseModel]
    arbitration: ArbitrationDecision
    consensus_log: list[AgentConsensusLog]
    skeleton: ChapterSkeleton
    consistency_report: ConsistencyReport
    retry_count: int


class DebateGraph:
    def __init__(
        self,
        agent_service: AgentNodeService,
        skeleton_builder: SkeletonBuilder,
        consistency_checker: ConsistencyChecker,
    ):
        self.agent_service = agent_service
        self.skeleton_builder = skeleton_builder
        self.consistency_checker = consistency_checker
        self.graph = self._build_graph()

    def _build_graph(self):
        workflow = StateGraph(DebateState)
        workflow.add_node("load_context", self._load_context)
        workflow.add_node("round1_propose", self._round1_propose)
        workflow.add_node("round2_debate", self._round2_debate)
        workflow.add_node("round3_arbitrate", self._round3_arbitrate)
        workflow.add_node("build_skeleton", self._build_skeleton)
        workflow.add_node("consistency_check", self._consistency_check)
        workflow.add_edge(START, "load_context")
        workflow.add_edge("load_context", "round1_propose")
        workflow.add_edge("round1_propose", "round2_debate")
        workflow.add_edge("round2_debate", "round3_arbitrate")
        workflow.add_edge("round3_arbitrate", "build_skeleton")
        workflow.add_edge("build_skeleton", "consistency_check")
        workflow.add_conditional_edges(
            "consistency_check",
            self._route_after_check,
            {"retry": "round1_propose", "done": END},
        )
        return workflow.compile()

    async def _load_context(self, state: DebateState):
        recalled_context = await self.agent_service.load_context(
            session_name=state["session_name"],
            chapter_goal=state["chapter_goal"],
            story_state=state["story_state"],
            world_model=state.get("world_model"),
            chapter_brief=state.get("chapter_brief"),
            lorebook_context=state.get("lorebook_context"),
            focus_threads=state["focus_threads"],
        )
        return {"recalled_context": recalled_context}

    async def _round1_propose(self, state: DebateState):
        proposals = await self.agent_service.build_proposals(
            chapter_goal=state["chapter_goal"],
            story_state=state["story_state"],
            world_model=state.get("world_model"),
            chapter_brief=state.get("chapter_brief"),
            lorebook_context=state.get("lorebook_context"),
            recalled_context=state["recalled_context"],
            focus_threads=state["focus_threads"],
        )
        log = [
            AgentConsensusLog(
                round_name="round1_propose",
                speaker=proposal.character_name,
                content=proposal.action_proposal,
            )
            for proposal in proposals
        ]
        return {"proposals": proposals, "consensus_log": log}

    async def _round2_debate(self, state: DebateState):
        critiques = await self.agent_service.build_critiques(
            chapter_goal=state["chapter_goal"],
            story_state=state["story_state"],
            world_model=state.get("world_model"),
            chapter_brief=state.get("chapter_brief"),
            lorebook_context=state.get("lorebook_context"),
            proposals=state["proposals"],
            recalled_context=state["recalled_context"],
        )
        log = list(state["consensus_log"])
        log.extend(
            AgentConsensusLog(
                round_name="round2_debate",
                speaker=item.character_name,
                content=item.critique,
            )
            for item in critiques
        )
        return {"critiques": critiques, "consensus_log": log}

    async def _round3_arbitrate(self, state: DebateState):
        decision = await self.agent_service.arbitrate(
            chapter_number=state["chapter_number"],
            chapter_goal=state["chapter_goal"],
            story_state=state["story_state"],
            world_model=state.get("world_model"),
            chapter_brief=state.get("chapter_brief"),
            lorebook_context=state.get("lorebook_context"),
            focus_threads=state["focus_threads"],
            proposals=state["proposals"],
            critiques=state["critiques"],
        )
        log = list(state["consensus_log"])
        log.append(
            AgentConsensusLog(
                round_name="round3_arbitrate",
                speaker="AuthorAgent",
                content=decision.winning_plan,
            )
        )
        return {"arbitration": decision, "consensus_log": log}

    async def _build_skeleton(self, state: DebateState):
        skeleton = await self.skeleton_builder.build(
            chapter_number=state["chapter_number"],
            chapter_goal=state["chapter_goal"],
            arbitration_result=state["arbitration"].model_dump(mode="json"),
            chapter_brief=state.get("chapter_brief"),
            lorebook_context=state.get("lorebook_context"),
            focus_thread_ids=[thread.id for thread in state["focus_threads"]],
            consensus_log=state["consensus_log"],
        )
        return {"skeleton": skeleton}

    async def _consistency_check(self, state: DebateState):
        report = self.consistency_checker.check(
            state["skeleton"],
            state["focus_threads"],
        )
        retry_count = state.get("retry_count", 0)
        if not report.passed:
            retry_count += 1
        return {"consistency_report": report, "retry_count": retry_count}

    def _route_after_check(self, state: DebateState) -> str:
        if (
            not state["consistency_report"].passed
            and state.get("retry_count", 0) <= self.consistency_checker.retry_limit
        ):
            return "retry"
        return "done"

    async def plan_chapter(
        self,
        *,
        session_name: str,
        chapter_number: int,
        chapter_goal: str,
        story_state: StoryWorldState,
        world_model: WorldModel | None = None,
        chapter_brief: ChapterBrief | None = None,
        lorebook_context: LorebookBundle | None = None,
        focus_threads: list[StoryThread],
    ) -> tuple[ChapterSkeleton, ConsistencyReport]:
        result = await self.graph.ainvoke(
            {
                "session_name": session_name,
                "chapter_number": chapter_number,
                "chapter_goal": chapter_goal,
                "story_state": story_state,
                "world_model": world_model,
                "chapter_brief": chapter_brief,
                "lorebook_context": lorebook_context,
                "focus_threads": focus_threads,
                "retry_count": 0,
            }
        )
        return result["skeleton"], result["consistency_report"]
