from __future__ import annotations

from pipeline.revival import CleanProseGate


def test_clean_prose_gate_passes_clean_prose() -> None:
    text = "沈照站在义庄门口，雨水顺着檐角砸下来。他没有回头，只把袖中的纸折得更紧。"

    result = CleanProseGate().check(text)

    assert result.passed is True
    assert result.hits == []
    assert result.chinese_char_count > 0


def test_clean_prose_gate_detects_ai_meta_text() -> None:
    text = (
        "沈照站在义庄门口，雨声越压越低。\n\n"
        "改写说明：这里强化了悬疑氛围。如果您需要，我可以继续。"
    )

    result = CleanProseGate().check(text)

    assert result.passed is False
    assert {hit.code for hit in result.hits} >= {
        "rewrite_note",
        "offer_more",
        "can_continue",
    }


def test_clean_prose_gate_detects_explanatory_wrappers() -> None:
    text = "以下是续写正文：\n\n作为AI，我会保持原作风格。\n\n总结：本章推进了冲突。"

    result = CleanProseGate().check(text)

    assert result.passed is False
    assert {hit.code for hit in result.hits} >= {
        "here_is",
        "ai_disclaimer",
        "summary_heading",
    }


def test_clean_prose_gate_detects_creation_notes() -> None:
    text = (
        "沈照站在义庄门口。\n\n"
        "创作说明：本段强化原作节奏。\n"
        "续写说明：后续可以继续推进。\n"
        "优化说明：压缩句子。\n"
        "模型附注：已尽量贴近原文。"
    )

    result = CleanProseGate().check(text)

    assert result.passed is False
    assert {hit.code for hit in result.hits} >= {
        "creation_note",
        "continuation_note",
        "polish_note",
        "model_note",
    }


def test_clean_prose_gate_can_enforce_minimum_length() -> None:
    result = CleanProseGate(min_chinese_chars=1000).check("沈照站在雨里。")

    assert result.passed is False
    assert result.hits[-1].code == "too_short"
