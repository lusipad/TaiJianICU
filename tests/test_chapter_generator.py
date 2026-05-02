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
