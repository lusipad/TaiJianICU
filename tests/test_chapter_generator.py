from pipeline.stage3_generation.chapter_generator import ChapterGenerator


def test_strip_output_shell_removes_model_wrappers() -> None:
    text = """以下为轻量润色稿：

---

话说宝玉病后初起。
"""

    assert ChapterGenerator.strip_output_shell(text) == "话说宝玉病后初起。"


def test_strip_output_shell_removes_markdown_fence() -> None:
    text = """```markdown
话说风过竹梢。
```"""

    assert ChapterGenerator.strip_output_shell(text) == "话说风过竹梢。"


def test_strip_output_shell_normalizes_minor_script_markers() -> None:
    text = "話說宝玉这日来至门前，说了几句话，过后仍不放心。"

    assert ChapterGenerator.strip_output_shell(text).startswith("话说宝玉")


def test_sanitize_generation_payload_removes_planning_analysis_tone() -> None:
    payload = {
        "chapter_theme": "芙蓉花影中的宿命之问",
        "scene_purpose": "用无声在场体现象征意义，避免结构性风险，让主题升华。",
        "nested": ["现实苦难成为活生生的注脚", "保留场面动作"],
    }

    sanitized = ChapterGenerator.sanitize_generation_payload(payload)

    assert "宿命" not in str(sanitized)
    assert "象征" not in str(sanitized)
    assert "结构性风险" not in str(sanitized)
    assert "主题升华" not in str(sanitized)
    assert "保留场面动作" in str(sanitized)


def test_revision_issue_guidance_expands_source_voice_failures() -> None:
    guidance = ChapterGenerator._revision_issue_guidance(
        [
            "繁简混杂：話說迎春",
            "低于源文本章节长度基线：3054/4257",
            "对白比例偏离原文：0.5120/0.1200",
        ]
    )

    assert "至少 4257 个中文字符" in guidance
    assert "低于该长度仍视为失败" in guidance
    assert "统一字形" in guidance
    assert "对白比例高于原文" in guidance


def test_revision_issue_guidance_rewrites_repeated_opening() -> None:
    guidance = ChapterGenerator._revision_issue_guidance(
        ["近章开头重复：与第115章开头高度一致"]
    )

    assert "重写当前正文开头前两段" in guidance
    assert "不得保留待修订正文开头的起句" in guidance
    assert "同一病后出门" in guidance
