from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

from core.models.style_profile import ExtractionSnapshot
from core.models.story_state import StoryThread


@dataclass(slots=True)
class StoryGraphChapter:
    chapter_number: int
    chapter_theme: str = ""
    status: str = ""
    threads_to_advance: list[str] = field(default_factory=list)
    threads_to_close: list[str] = field(default_factory=list)
    participants: list[str] = field(default_factory=list)


def _escape_label(value: str) -> str:
    return value.replace('"', "'").replace("\n", "\\n")


def _node_id(prefix: str, value: str) -> str:
    digest = hashlib.sha1(f"{prefix}:{value}".encode("utf-8")).hexdigest()[:10]
    return f"{prefix}_{digest}"


def build_story_mermaid(
    session_name: str,
    snapshot: ExtractionSnapshot | None,
    threads: list[StoryThread],
    chapters: list[StoryGraphChapter] | None = None,
) -> str:
    lines = ["graph TD"]
    root_label = snapshot.story_state.title if snapshot and snapshot.story_state.title else session_name
    lines.append(f'  root["{_escape_label(root_label)}"]')
    character_nodes: dict[str, str] = {}
    thread_nodes: dict[str, str] = {}

    if snapshot:
        for index, character in enumerate(snapshot.story_state.main_characters, start=1):
            node = f"char_{index}"
            character_nodes[character.name] = node
            lines.append(
                f'  {node}["{_escape_label(character.name)}\\n{_escape_label(character.role)}"]'
            )
            lines.append(f"  root --> {node}")
        for index, relation in enumerate(snapshot.story_state.major_relationships, start=1):
            node = f"rel_{index}"
            lines.append(f'  {node}["{_escape_label(relation)}"]')
            lines.append(f"  root -.-> {node}")

    for index, thread in enumerate(threads, start=1):
        node = f"thread_{index}"
        thread_nodes[thread.id] = node
        label = (
            f"{_escape_label(thread.id)}\\n"
            f"{_escape_label(thread.description)}\\n"
            f"{_escape_label(thread.status)}"
        )
        lines.append(f'  {node}["{label}"]')
        lines.append(f"  root --> {node}")

    if chapters:
        for chapter in chapters:
            chapter_node = f"chapter_{chapter.chapter_number}"
            theme = chapter.chapter_theme or chapter.status or "未命名章节"
            lines.append(
                f'  {chapter_node}["第{chapter.chapter_number}章\\n{_escape_label(theme)}"]'
            )
            lines.append(f"  root --> {chapter_node}")

            for thread_id in chapter.threads_to_advance:
                thread_node = thread_nodes.get(thread_id)
                if thread_node is not None:
                    lines.append(f"  {chapter_node} -->|推进| {thread_node}")

            for thread_id in chapter.threads_to_close:
                thread_node = thread_nodes.get(thread_id)
                if thread_node is not None:
                    lines.append(f"  {chapter_node} -.->|收束| {thread_node}")

            for participant in chapter.participants:
                character_node = character_nodes.get(participant)
                if character_node is None:
                    character_node = _node_id("participant", participant)
                    lines.append(f'  {character_node}["{_escape_label(participant)}"]')
                    lines.append(f"  root --> {character_node}")
                    character_nodes[participant] = character_node
                lines.append(f"  {chapter_node} --> {character_node}")

    return "\n".join(lines) + "\n"


def export_story_mermaid(
    output_path: Path,
    session_name: str,
    snapshot: ExtractionSnapshot | None,
    threads: list[StoryThread],
    chapters: list[StoryGraphChapter] | None = None,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        build_story_mermaid(session_name, snapshot, threads, chapters),
        encoding="utf-8",
    )
    return output_path
