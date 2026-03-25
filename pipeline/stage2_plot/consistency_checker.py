from __future__ import annotations

from pydantic import BaseModel, Field

from core.models.skeleton import ChapterSkeleton
from core.models.story_state import StoryThread


class ConsistencyReport(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)


class ConsistencyChecker:
    def __init__(self, retry_limit: int = 2):
        self.retry_limit = retry_limit

    def check(
        self,
        skeleton: ChapterSkeleton,
        focus_threads: list[StoryThread],
    ) -> ConsistencyReport:
        issues: list[str] = []
        if len(skeleton.scenes) < 3:
            issues.append("场景数量过少，无法支撑完整章节推进。")
        if len(skeleton.scenes) > 8:
            issues.append("场景数量过多，章节节奏可能过碎。")
        if any(not scene.participants for scene in skeleton.scenes):
            issues.append("存在未指定参与角色的场景。")
        if focus_threads:
            required = {thread.id for thread in focus_threads}
            touched = set(skeleton.threads_to_advance) | set(skeleton.threads_to_close)
            if not touched.intersection(required):
                issues.append("本章没有推进任何指定伏笔。")
        return ConsistencyReport(passed=not issues, issues=issues)
