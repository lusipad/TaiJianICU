from __future__ import annotations

import re
from dataclasses import dataclass

from core.models.revival import CleanProseGateResult, CleanProseHit


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
