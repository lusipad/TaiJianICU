from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from statistics import median

from config.settings import AppSettings, render_prompt
from core.llm.litellm_client import LiteLLMService
from core.models.arc_outline import ArcOutline
from core.models.lorebook import LorebookBundle
from core.models.revival import (
    BlindChallenge,
    BlindChallengeExcerpt,
    BlindJudgeDecision,
    BlindJudgeReport,
    BlindJudgeRound,
    CharacterVoiceRule,
    CleanProseGateResult,
    CleanProseHit,
    DirectorArcOption,
    DirectorArcOptions,
    RevivalDiagnosis,
    RevivalChapter,
    RevivalStyleBible,
    RevivalWorkspaceArtifacts,
    StyleMetrics,
    WorkSkill,
    WorkSkillEvidenceRef,
)
from core.models.style_profile import ExtractionSnapshot
from core.models.world_model import WorldModel


_CHINESE_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_SENTENCE_RE = re.compile(r"[^。！？!?；;\n]+[。！？!?；;]?")
_CHAPTER_HEADING_RE = re.compile(
    r"^\s*第([一二三四五六七八九十百千万〇零两\d]+)回(?:[ \t　]+([^\r\n]*)|[ \t　]*$)",
    re.M,
)

MODERN_FORBIDDEN_WORDS = [
    "心理压力",
    "关系变化",
    "信息反转",
    "情绪价值",
    "创伤",
    "压迫感",
    "安全感",
    "自我认同",
    "边界感",
    "原生家庭",
    "精神崩塌",
    "压迫机制",
    "家庭暴力",
    "权力结构",
    "核心伏笔",
    "主线推进",
    "人物弧光",
]

_SIMPLIFIED_MARKERS = set("这为来个门们说时过后")
_TRADITIONAL_MARKERS = set("這為來個門們說時過後")


@dataclass(frozen=True)
class ForbiddenPattern:
    code: str
    label: str
    pattern: re.Pattern[str]


def _chinese_char_count(text: str) -> int:
    return len(_CHINESE_CHAR_RE.findall(text))


def _take_chinese_chars(text: str, target_chars: int) -> tuple[str, int]:
    target_chars = max(1, target_chars)
    excerpt_chars: list[str] = []
    chinese_count = 0
    for char in text:
        excerpt_chars.append(char)
        if _CHINESE_CHAR_RE.match(char):
            chinese_count += 1
        if chinese_count >= target_chars:
            break
    return "".join(excerpt_chars).strip(), chinese_count


def _chinese_numeral_to_int(value: str) -> int | None:
    if value.isdigit():
        return int(value)
    digits = {
        "零": 0,
        "〇": 0,
        "一": 1,
        "二": 2,
        "两": 2,
        "三": 3,
        "四": 4,
        "五": 5,
        "六": 6,
        "七": 7,
        "八": 8,
        "九": 9,
    }
    units = {"十": 10, "百": 100, "千": 1000, "万": 10000}
    total = 0
    section = 0
    number = 0
    for char in value:
        if char in digits:
            number = digits[char]
        elif char in units:
            unit = units[char]
            if unit == 10000:
                section = (section + number) * unit
                total += section
                section = 0
            else:
                section += (number or 1) * unit
            number = 0
        else:
            return None
    return total + section + number


class ChapterSplitter:
    def split(self, source_text: str) -> list[RevivalChapter]:
        matches = list(_CHAPTER_HEADING_RE.finditer(source_text))
        if not matches:
            return [
                RevivalChapter(
                    chapter_number=1,
                    title="全文",
                    text=source_text.strip(),
                    start_char=0,
                    end_char=len(source_text),
                )
            ]

        chapters: list[RevivalChapter] = []
        for index, match in enumerate(matches):
            next_start = matches[index + 1].start() if index + 1 < len(matches) else len(source_text)
            body = source_text[match.end() : next_start].strip()
            heading_title = (match.group(2) or "").strip()
            chapters.append(
                RevivalChapter(
                    chapter_number=_chinese_numeral_to_int(match.group(1)),
                    title=heading_title,
                    text=body,
                    start_char=match.start(),
                    end_char=next_start,
                )
            )
        return self._dedupe_adjacent_headings(chapters)

    @staticmethod
    def _dedupe_adjacent_headings(chapters: list[RevivalChapter]) -> list[RevivalChapter]:
        deduped: list[RevivalChapter] = []
        for chapter in chapters:
            previous = deduped[-1] if deduped else None
            if (
                previous is not None
                and previous.chapter_number == chapter.chapter_number
                and previous.title == chapter.title
            ):
                deduped[-1] = chapter
                continue
            deduped.append(chapter)
        return deduped


class StyleBibleBuilder:
    def build(
        self,
        source_text: str,
        *,
        work_title: str | None = None,
        character_names: list[str] | None = None,
    ) -> RevivalStyleBible:
        metrics = self.measure(source_text)
        patterns = [
            item
            for item in ["且说", "却说", "话说", "谁知", "原来", "一面", "不觉", "说着"]
            if item in source_text
        ]
        names = character_names or self._infer_character_names(source_text)
        return RevivalStyleBible(
            generated_at=datetime.now(timezone.utc),
            work_title=work_title,
            narrative_patterns=patterns,
            style_metrics=metrics,
            forbidden_words=MODERN_FORBIDDEN_WORDS,
            character_voice_cards=[
                CharacterVoiceRule(character_name=name, voice_summary="待人工校准")
                for name in names
            ],
        )

    def measure(self, text: str) -> StyleMetrics:
        chinese_count = _chinese_char_count(text)
        sentences = [
            sentence
            for sentence in _SENTENCE_RE.findall(text)
            if _chinese_char_count(sentence) > 0
        ]
        avg_sentence_length = (
            sum(_chinese_char_count(sentence) for sentence in sentences) / len(sentences)
            if sentences
            else 0.0
        )
        dialogue_chars = sum(
            _chinese_char_count(match.group(0))
            for match in re.finditer(r"[“「『][^”」』]{1,400}[”」』]", text)
        )
        density = {
            word: (text.count(word) / chinese_count if chinese_count else 0.0)
            for word in ["的", "了", "着", "这", "是"]
        }
        return StyleMetrics(
            chinese_char_count=chinese_count,
            avg_sentence_length=round(avg_sentence_length, 2),
            dialogue_ratio=round(dialogue_chars / chinese_count, 4) if chinese_count else 0.0,
            function_word_density=density,
        )

    @staticmethod
    def _infer_character_names(source_text: str) -> list[str]:
        known_names = ["宝玉", "黛玉", "宝钗", "袭人", "王夫人", "凤姐", "迎春", "香菱"]
        return [name for name in known_names if name in source_text]


class RevivalWorkspaceBuilder:
    def __init__(
        self,
        chapter_splitter: ChapterSplitter | None = None,
        style_bible_builder: StyleBibleBuilder | None = None,
    ):
        self.chapter_splitter = chapter_splitter or ChapterSplitter()
        self.style_bible_builder = style_bible_builder or StyleBibleBuilder()

    def build(
        self,
        source_text: str,
        *,
        source_digest: str | None = None,
        work_title: str | None = None,
        character_names: list[str] | None = None,
    ) -> RevivalWorkspaceArtifacts:
        digest = source_digest or hashlib.sha256(source_text.encode("utf-8")).hexdigest()
        chapters = self.chapter_splitter.split(source_text)
        style_bible = self.style_bible_builder.build(
            source_text,
            work_title=work_title,
            character_names=character_names,
        )
        return RevivalWorkspaceArtifacts(
            source_digest=digest,
            chapters=chapters,
            style_bible=style_bible,
            forbidden_words=style_bible.forbidden_words,
        )


class CleanProseGate:
    def __init__(
        self,
        min_chinese_chars: int = 0,
        *,
        forbidden_words: list[str] | None = None,
        style_metrics: StyleMetrics | None = None,
    ):
        self.min_chinese_chars = max(0, min_chinese_chars)
        self.forbidden_words = forbidden_words or MODERN_FORBIDDEN_WORDS
        self.style_metrics = style_metrics
        self._patterns = [
            ForbiddenPattern("rewrite_note", "改写说明", re.compile(r"改写说明")),
            ForbiddenPattern("creation_note", "创作说明", re.compile(r"创作说明")),
            ForbiddenPattern("continuation_note", "续写说明", re.compile(r"续写说明")),
            ForbiddenPattern("polish_note", "优化说明", re.compile(r"优化说明")),
            ForbiddenPattern("model_note", "模型附注", re.compile(r"模型附注")),
            ForbiddenPattern("offer_more", "如果您需要", re.compile(r"如果[你您]需要")),
            ForbiddenPattern("can_continue", "我可以继续", re.compile(r"我可以继续")),
            ForbiddenPattern("ai_disclaimer", "AI 身份说明", re.compile(r"作为\s*(?:AI|人工智能|一个\s*AI)", re.I)),
            ForbiddenPattern("here_is", "以下是", re.compile(r"^\s*以下是", re.M)),
            ForbiddenPattern("summary_heading", "总结标题", re.compile(r"^\s*总结\s*[:：]", re.M)),
            ForbiddenPattern("explanation_heading", "说明标题", re.compile(r"^\s*说明\s*[:：]", re.M)),
            ForbiddenPattern("markdown_fence", "Markdown 代码块", re.compile(r"```")),
            ForbiddenPattern("chapter_meta", "章节元叙述", re.compile(r"(?:本章|这一章|上文|下文).{0,16}(?:推进|照应|主题|伏笔|剧情)")),
            ForbiddenPattern("theme_explanation", "主题阐释句", re.compile(r"(?:体现|说明|揭示|象征着).{0,24}(?:主题|命运|压迫|结构|伏笔|弧光)")),
            ForbiddenPattern("analysis_tone", "分析腔", re.compile(r"(?:人物命运|精神崩塌|压迫机制|权力结构|主线推进|人物弧光)")),
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
        hits.extend(self._forbidden_word_hits(text))
        chinese_char_count = _chinese_char_count(text)
        if self._has_simplified_traditional_mix(text):
            hits.append(
                CleanProseHit(
                    code="script_mixed",
                    label="繁简混杂",
                    excerpt=self._first_chars(text, 40),
                )
            )
        if self.min_chinese_chars and chinese_char_count < self.min_chinese_chars:
            hits.append(
                CleanProseHit(
                    code="too_short",
                    label="正文过短",
                    excerpt=f"{chinese_char_count}/{self.min_chinese_chars}",
                )
            )
        if self.style_metrics and chinese_char_count >= 80:
            hits.extend(self._metric_hits(text))
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

    def _forbidden_word_hits(self, text: str) -> list[CleanProseHit]:
        hits: list[CleanProseHit] = []
        for word in self.forbidden_words:
            if not word or word not in text:
                continue
            index = text.index(word)
            hits.append(
                CleanProseHit(
                    code="modern_word",
                    label=f"现代抽象词：{word}",
                    excerpt=self._excerpt(text, index, index + len(word)),
                )
            )
        return hits

    def _metric_hits(self, text: str) -> list[CleanProseHit]:
        current = StyleBibleBuilder().measure(text)
        expected = self.style_metrics
        if expected is None:
            return []
        hits: list[CleanProseHit] = []
        if expected.avg_sentence_length > 0:
            ratio = current.avg_sentence_length / expected.avg_sentence_length
            if ratio > 2.5 or ratio < 0.35:
                hits.append(
                    CleanProseHit(
                        code="avg_sentence_length_drift",
                        label="平均句长偏离原文",
                        excerpt=(
                            f"{current.avg_sentence_length:.2f}/"
                            f"{expected.avg_sentence_length:.2f}"
                        ),
                    )
                )
        if abs(current.dialogue_ratio - expected.dialogue_ratio) > 0.35:
            hits.append(
                CleanProseHit(
                    code="dialogue_ratio_drift",
                    label="对白比例偏离原文",
                    excerpt=f"{current.dialogue_ratio:.4f}/{expected.dialogue_ratio:.4f}",
                )
            )
        for word, expected_density in expected.function_word_density.items():
            current_density = current.function_word_density.get(word, 0.0)
            if abs(current_density - expected_density) > max(0.06, expected_density * 4):
                hits.append(
                    CleanProseHit(
                        code="function_word_density_drift",
                        label=f"虚词密度偏离：{word}",
                        excerpt=f"{current_density:.4f}/{expected_density:.4f}",
                    )
                )
                break
        return hits

    @staticmethod
    def _has_simplified_traditional_mix(text: str) -> bool:
        return bool(_SIMPLIFIED_MARKERS & set(text)) and bool(_TRADITIONAL_MARKERS & set(text))

    @staticmethod
    def _first_chars(text: str, count: int) -> str:
        return text[:count].replace("\n", "\\n")


class SourceVoiceGate:
    _EXPLANATORY_PHRASES = [
        "像是",
        "说不清",
        "说不清道不明",
        "一步一步变成现实",
        "这现实",
        "命运",
        "象征",
        "主题",
        "结构",
    ]

    def __init__(
        self,
        *,
        min_chinese_chars: int,
        style_metrics: StyleMetrics,
        forbidden_words: list[str] | None = None,
    ):
        self.min_chinese_chars = max(0, min_chinese_chars)
        self.clean_gate = CleanProseGate(
            min_chinese_chars=self.min_chinese_chars,
            forbidden_words=forbidden_words,
            style_metrics=style_metrics,
        )

    @classmethod
    def from_source_text(cls, source_text: str) -> SourceVoiceGate:
        chapters = [
            chapter.text
            for chapter in ChapterSplitter().split(source_text)
            if _chinese_char_count(chapter.text) >= 200
        ]
        if not chapters:
            return cls(
                min_chinese_chars=0,
                style_metrics=StyleBibleBuilder().measure(source_text),
            )
        chapter_lengths = [_chinese_char_count(text) for text in chapters]
        min_chinese_chars = int(median(chapter_lengths) * 0.7)
        return cls(
            min_chinese_chars=min_chinese_chars,
            style_metrics=StyleBibleBuilder().measure("\n".join(chapters)),
        )

    def check(self, text: str) -> CleanProseGateResult:
        result = self.clean_gate.check(text)
        hits = [
            hit.model_copy(
                update={
                    "code": "source_baseline_too_short",
                    "label": "低于源文本章节长度基线",
                }
            )
            if hit.code == "too_short"
            else hit
            for hit in result.hits
        ]
        explanatory_count = sum(text.count(phrase) for phrase in self._EXPLANATORY_PHRASES)
        chinese_count = _chinese_char_count(text)
        if chinese_count and explanatory_count / chinese_count > 0.004:
            hits.append(
                CleanProseHit(
                    code="explanatory_prose_drift",
                    label="解释性抒情腔偏离源文本",
                    excerpt=f"{explanatory_count}/{chinese_count}",
                )
            )
        return result.model_copy(
            update={
                "status": "fail" if hits else "pass",
                "hits": hits,
            }
        )


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
        world_rules = list(
            dict.fromkeys(
                item
                for item in [*story.world_rules, *world_model.power_system_rules]
                if item
            )
        )
        return WorkSkill(
            source_digest=source_digest,
            generated_at=datetime.now(timezone.utc),
            work_title=story.title or world_model.title,
            voice_rules=voice_rules,
            rhythm_rules=rhythm_rules,
            character_voice_map=character_voice_map,
            world_rules=world_rules,
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


class RevivalDiagnosisBuilder:
    def build(
        self,
        *,
        gate_result: CleanProseGateResult,
        quality_score: float | None,
        retry_count: int,
    ) -> RevivalDiagnosis:
        failure_reasons = [hit.label for hit in gate_result.hits]
        status = "pass" if gate_result.passed else "fail"
        recommended_fix = ""
        if not gate_result.passed:
            recommended_fix = "重新生成正文，并禁止输出说明、总结、续写建议或 AI 身份表达。"
        return RevivalDiagnosis(
            status=status,
            gate_results=[gate_result],
            contamination_hits=gate_result.hits,
            voice_fit=quality_score,
            plot_alignment=quality_score,
            character_fit=quality_score,
            retry_count=retry_count,
            failure_reasons=failure_reasons,
            recommended_fix=recommended_fix,
        )


class BlindChallengeBuilder:
    def build(
        self,
        chapter_text: str,
        target_chars: int = 1000,
        *,
        source_text: str | None = None,
        source_chapters: list[RevivalChapter] | None = None,
        canon_excerpt_count: int = 3,
    ) -> BlindChallenge:
        excerpt, chinese_count = _take_chinese_chars(chapter_text, target_chars)
        generated = BlindChallengeExcerpt(
            excerpt_id="generated",
            text=excerpt,
            excerpt_char_count=chinese_count,
            source_note="generated",
        )
        canon_excerpts = self._canon_excerpts(
            target_chars=target_chars,
            source_text=source_text,
            source_chapters=source_chapters,
            canon_excerpt_count=canon_excerpt_count,
        )
        labeled_excerpts = self._shuffle_and_label([generated, *canon_excerpts], excerpt)
        generated_excerpt_id = next(
            (item.excerpt_id for item in labeled_excerpts if item.source_note == "generated"),
            None,
        )
        return BlindChallenge(
            excerpt_text=excerpt,
            excerpt_char_count=chinese_count,
            source_label_hidden=True,
            excerpts=[
                item.model_copy(update={"source_note": ""}) for item in labeled_excerpts
            ],
            generated_excerpt_id=generated_excerpt_id,
        )

    def _canon_excerpts(
        self,
        *,
        target_chars: int,
        source_text: str | None,
        source_chapters: list[RevivalChapter] | None,
        canon_excerpt_count: int,
    ) -> list[BlindChallengeExcerpt]:
        sources: list[tuple[str, str]] = []
        if source_chapters:
            for chapter in source_chapters:
                if _chinese_char_count(chapter.text) >= max(20, target_chars // 2):
                    note = (
                        f"chapter_{chapter.chapter_number}"
                        if chapter.chapter_number is not None
                        else "chapter"
                    )
                    sources.append((note, chapter.text))
        elif source_text:
            sources.append(("source", source_text))

        excerpts: list[BlindChallengeExcerpt] = []
        for index, (note, text) in enumerate(sources):
            if len(excerpts) >= canon_excerpt_count:
                break
            excerpt, count = _take_chinese_chars(text.strip(), target_chars)
            if count == 0:
                continue
            excerpts.append(
                BlindChallengeExcerpt(
                    excerpt_id=f"canon_{index + 1}",
                    text=excerpt,
                    excerpt_char_count=count,
                    source_note=note,
                )
            )

        if len(excerpts) < canon_excerpt_count and source_text:
            excerpts.extend(
                self._fallback_windows(
                    source_text,
                    target_chars=target_chars,
                    start_index=len(excerpts),
                    needed=canon_excerpt_count - len(excerpts),
                )
            )
        return excerpts[:canon_excerpt_count]

    def _fallback_windows(
        self,
        source_text: str,
        *,
        target_chars: int,
        start_index: int,
        needed: int,
    ) -> list[BlindChallengeExcerpt]:
        clean_text = source_text.strip()
        if not clean_text:
            return []
        windows: list[BlindChallengeExcerpt] = []
        starts = [
            0,
            max(0, len(clean_text) // 2),
            max(0, len(clean_text) - target_chars * 2),
        ]
        for offset in starts:
            if len(windows) >= needed:
                break
            excerpt, count = _take_chinese_chars(clean_text[offset:], target_chars)
            if count == 0:
                continue
            number = start_index + len(windows) + 1
            windows.append(
                BlindChallengeExcerpt(
                    excerpt_id=f"canon_{number}",
                    text=excerpt,
                    excerpt_char_count=count,
                    source_note=f"source_window_{number}",
                )
            )
        return windows

    @staticmethod
    def _shuffle_and_label(
        excerpts: list[BlindChallengeExcerpt],
        seed_text: str,
    ) -> list[BlindChallengeExcerpt]:
        seed = hashlib.sha256(seed_text.encode("utf-8")).hexdigest()
        ordered = sorted(
            excerpts,
            key=lambda item: hashlib.sha256(f"{seed}:{item.excerpt_id}".encode("utf-8")).hexdigest(),
        )
        labels = ["A", "B", "C", "D", "E", "F"]
        return [
            item.model_copy(update={"excerpt_id": labels[index]})
            for index, item in enumerate(ordered)
        ]


class BlindJudge:
    def __init__(
        self,
        settings: AppSettings,
        llm_service: LiteLLMService,
    ):
        self.settings = settings
        self.llm_service = llm_service

    async def judge(
        self,
        *,
        challenge: BlindChallenge,
        style_bible: RevivalStyleBible,
        round_number: int = 1,
    ) -> BlindJudgeRound:
        if not challenge.generated_excerpt_id or not challenge.excerpts:
            decision = BlindJudgeDecision(
                suspected_excerpt_id="",
                confidence=0.0,
                reason="盲测挑战缺少可判别片段。",
            )
            return BlindJudgeRound(
                round_number=round_number,
                generated_excerpt_id=challenge.generated_excerpt_id,
                decision=decision,
                passed=True,
            )

        prompt = render_prompt(
            "revival/blind_judge.txt",
            style_bible=style_bible.model_dump(mode="json"),
            excerpts=[
                {
                    "excerpt_id": item.excerpt_id,
                    "text": item.text,
                    "excerpt_char_count": item.excerpt_char_count,
                }
                for item in challenge.excerpts
            ],
        )
        decision = await self.llm_service.complete_structured(
            model=self.settings.models.quality_model,
            messages=[{"role": "user", "content": prompt}],
            response_model=BlindJudgeDecision,
            temperature=0.1,
            max_tokens=1200,
            operation="revival_blind_judge",
        )
        assert isinstance(decision, BlindJudgeDecision)
        return self.evaluate_decision(
            challenge=challenge,
            decision=decision,
            round_number=round_number,
            confidence_threshold=self.settings.tuning.blind_judge_confidence_threshold,
        )

    @staticmethod
    def evaluate_decision(
        *,
        challenge: BlindChallenge,
        decision: BlindJudgeDecision,
        round_number: int,
        confidence_threshold: float,
    ) -> BlindJudgeRound:
        generated_id = challenge.generated_excerpt_id
        caught_generated = (
            bool(generated_id)
            and decision.suspected_excerpt_id == generated_id
            and decision.confidence >= confidence_threshold
        )
        failure_reasons: list[str] = []
        if caught_generated:
            failure_reasons.append(
                f"盲测判别器以 {decision.confidence:.2f} 置信度识别出生成片段 {generated_id}。"
            )
            if decision.reason:
                failure_reasons.append(decision.reason)
            failure_reasons.extend(decision.unlike_sentences[:3])
            failure_reasons.extend(decision.rewrite_guidance[:3])
        return BlindJudgeRound(
            round_number=round_number,
            generated_excerpt_id=generated_id,
            decision=decision,
            passed=not caught_generated,
            failure_reasons=failure_reasons,
        )

    @staticmethod
    def report(
        *,
        rounds: list[BlindJudgeRound],
        confidence_threshold: float,
    ) -> BlindJudgeReport:
        if not rounds:
            return BlindJudgeReport(
                status="skipped",
                confidence_threshold=confidence_threshold,
                rounds=[],
            )
        return BlindJudgeReport(
            status="pass" if rounds[-1].passed else "fail",
            confidence_threshold=confidence_threshold,
            rounds=rounds,
        )
