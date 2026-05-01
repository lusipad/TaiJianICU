from __future__ import annotations

from core.models.revival import StyleMetrics
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


def test_clean_prose_gate_detects_modern_abstract_words() -> None:
    result = CleanProseGate().check("黛玉忽觉自己没有安全感，又想索取情绪价值。")

    assert result.passed is False
    assert {hit.code for hit in result.hits} >= {"modern_word"}


def test_clean_prose_gate_detects_chapter_meta_analysis() -> None:
    text = (
        "本章推进宝玉的精神崩塌，并揭示家族体面背后的压迫结构。"
        "这一安排象征着人物命运的核心伏笔。"
    )

    result = CleanProseGate().check(text)

    assert result.passed is False
    assert {
        "chapter_meta",
        "theme_explanation",
        "analysis_tone",
        "modern_word",
    } <= {hit.code for hit in result.hits}


def test_clean_prose_gate_detects_script_mix() -> None:
    result = CleanProseGate().check("这人走到門前，說了一句。")

    assert result.passed is False
    assert "script_mixed" in {hit.code for hit in result.hits}


def test_clean_prose_gate_detects_style_metric_drift() -> None:
    baseline = StyleMetrics(
        chinese_char_count=2000,
        avg_sentence_length=8,
        dialogue_ratio=0.2,
        function_word_density={"的": 0.01},
    )
    text = "他站在门前想着那些极其复杂而又漫长的心理压力与关系变化。" * 8

    result = CleanProseGate(style_metrics=baseline).check(text)

    assert result.passed is False
    assert {
        "avg_sentence_length_drift",
        "modern_word",
    } <= {hit.code for hit in result.hits}
