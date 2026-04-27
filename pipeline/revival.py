from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone

from core.models.arc_outline import ArcOutline
from core.models.lorebook import LorebookBundle
from core.models.revival import (
    CharacterVoiceRule,
    CleanProseGateResult,
    CleanProseHit,
    DirectorArcOption,
    DirectorArcOptions,
    WorkSkill,
    WorkSkillEvidenceRef,
)
from core.models.style_profile import ExtractionSnapshot
from core.models.world_model import WorldModel


_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")


@dataclass(frozen=True)
class ForbiddenPattern:
    code: str
    label: str
    pattern: re.Pattern[str]


class CleanProseGate:
    def __init__(self, min_chinese_chars: int = 0):
        self.min_chinese_chars = max(0, min_chinese_chars)
        self._patterns = [
            ForbiddenPattern("rewrite_note", "改写说明", re.compile(r"改写说明")),
            ForbiddenPattern("offer_more", "如果您需要", re.compile(r"如果[你您]需要")),
            ForbiddenPattern("can_continue", "我可以继续", re.compile(r"我可以继续")),
            ForbiddenPattern("ai_disclaimer", "AI 身份说明", re.compile(r"作为\s*(?:AI|人工智能|一个\s*AI)", re.I)),
            ForbiddenPattern("here_is", "以下是", re.compile(r"^\s*以下是", re.M)),
            ForbiddenPattern("summary_heading", "总结标题", re.compile(r"^\s*总结\s*[:：]", re.M)),
            ForbiddenPattern("explanation_heading", "说明标题", re.compile(r"^\s*说明\s*[:：]", re.M)),
            ForbiddenPattern("markdown_fence", "Markdown 代码块", re.compile(r"```")),
        ]

    def check(self, text: str) -> CleanProseGateResult:
        hits = [
            CleanProseHit(
                code=item.code,
                label=item.label,
                excerpt=self._excerpt(text, match.start(), match.end()),
            )
            for item in self._patterns
            for match in item.pattern.finditer(text)
        ]
        chinese_char_count = len(_CHINESE_CHAR_RE.findall(text))
        if self.min_chinese_chars and chinese_char_count < self.min_chinese_chars:
            hits.append(
                CleanProseHit(
                    code="too_short",
                    label="正文过短",
                    excerpt=f"{chinese_char_count}/{self.min_chinese_chars}",
                )
            )
        return CleanProseGateResult(
            status="fail" if hits else "pass",
            chinese_char_count=chinese_char_count,
            hits=hits,
        )

    @staticmethod
    def _excerpt(text: str, start: int, end: int) -> str:
        excerpt_start = max(0, start - 20)
        excerpt_end = min(len(text), end + 20)
        return text[excerpt_start:excerpt_end].replace("\n", "\\n")


def digest_payload(payload: object) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class WorkSkillBuilder:
    def build(
        self,
        *,
        snapshot: ExtractionSnapshot,
        world_model: WorldModel,
        lorebook: LorebookBundle,
        source_digest: str,
    ) -> WorkSkill:
        style = snapshot.style_profile
        story = snapshot.story_state
        voice_rules = [
            item
            for item in [
                f"叙事人称：{style.narrative_person}",
                f"整体语气：{'、'.join(style.tone_keywords)}" if style.tone_keywords else "",
                style.summary,
                f"对白风格：{style.dialogue_style}" if style.dialogue_style else "",
            ]
            if item
        ]
        rhythm_rules = [
            item
            for item in [
                f"节奏：{style.pacing}",
                style.sentence_rhythm,
                *style.signature_devices,
            ]
            if item
        ]
        character_voice_map = [
            CharacterVoiceRule(
                character_name=item.name,
                voice_summary=item.speech_style or item.last_known_state,
                diction_rules=item.personality_traits,
                taboo_moves=[],
            )
            for item in story.main_characters
            if item.name.strip()
        ]
        evidence_refs = [
            WorkSkillEvidenceRef(source=entry.entry_id, note=entry.title)
            for entry in lorebook.entries[:8]
        ]
        return WorkSkill(
            source_digest=source_digest,
            generated_at=datetime.now(timezone.utc),
            work_title=story.title or world_model.title,
            voice_rules=voice_rules,
            rhythm_rules=rhythm_rules,
            character_voice_map=character_voice_map,
            world_rules=[*story.world_rules, *world_model.power_system_rules],
            open_threads=[
                f"{thread.id}: {thread.description}"
                for thread in story.unresolved_threads
                if thread.status != "closed"
            ],
            forbidden_moves=style.taboo_patterns,
            evidence_refs=evidence_refs,
        )


class RevivalArcPlanner:
    def plan_options(
        self,
        *,
        work_skill: WorkSkill,
        snapshot: ExtractionSnapshot,
        world_model: WorldModel,
        arc_outline: ArcOutline,
    ) -> DirectorArcOptions:
        story = snapshot.story_state
        main_character = story.main_characters[0].name if story.main_characters else "主角"
        focus_thread = next(
            (thread.description for thread in story.unresolved_threads if thread.status != "closed"),
            arc_outline.arc_goal or story.summary or "推进主线冲突",
        )
        active_conflict = story.active_conflicts[0] if story.active_conflicts else focus_thread
        hard_rules = work_skill.forbidden_moves[:3] or story.world_rules[:3]
        options = [
            DirectorArcOption(
                id="arc_conservative",
                title="顺势续燃",
                character_focus=[main_character],
                emotional_direction="保持原书惯性，先稳住人物声口和断点情绪。",
                must_happen=[focus_thread],
                must_not_break=hard_rules,
                consequences=["读感最稳", "爆点较克制", "适合先验证作者节奏"],
                risk_flags=["可能不够惊艳"],
            ),
            DirectorArcOption(
                id="arc_emotional",
                title="暗压升温",
                character_focus=[main_character],
                emotional_direction="让人物关系或内心压力明显升温，但不直接揭底。",
                must_happen=[active_conflict],
                must_not_break=hard_rules,
                consequences=["人物张力更强", "更容易看出角色声口", "需要避免情绪过满"],
                risk_flags=["可能比原书更用力"],
            ),
            DirectorArcOption(
                id="arc_pressure_turn",
                title="局势逼转",
                character_focus=[main_character],
                emotional_direction="用外部压力推动剧情转向，让角色被迫做选择。",
                must_happen=[arc_outline.arc_goal or focus_thread],
                must_not_break=hard_rules,
                consequences=["剧情推进更明显", "适合测试 plot alignment", "会更考验世界约束"],
                risk_flags=["可能偏离原书慢热节奏"],
            ),
        ]
        return DirectorArcOptions(
            generated_at=datetime.now(timezone.utc),
            options=options,
        )
