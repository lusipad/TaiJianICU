from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path


def _data_arg(source: str, target: str) -> str:
    separator = ";" if sys.platform == "win32" else ":"
    return f"{source}{separator}{target}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", default=sys.executable)
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    subprocess.run([args.python, "-m", "pip", "install", "-e", ".", "pyinstaller"], cwd=repo_root, check=True)

    command = [
        args.python,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--name",
        "TaiJianICU",
        "--onefile",
        "--windowed",
        "--add-data",
        _data_arg("webapp/static", "webapp/static"),
        "--add-data",
        _data_arg("config/prompts", "config/prompts"),
        "--add-data",
        _data_arg("config/references", "config/references"),
        "--collect-all",
        "lightrag",
        "--collect-all",
        "litellm",
        "--collect-all",
        "deepeval",
        "--collect-all",
        "instructor",
        "--collect-all",
        "langchain_text_splitters",
        "--collect-all",
        "langgraph",
        "--hidden-import",
        "webapp.app",
        "--hidden-import",
        "cli.main",
        "--hidden-import",
        "cli.standalone_cmd",
        "--hidden-import",
        "PySide6.QtWebEngineCore",
        "--hidden-import",
        "PySide6.QtWebEngineWidgets",
        "scripts/standalone_entry.py",
    ]
    subprocess.run(command, cwd=repo_root, check=True)

    env_example = repo_root / ".env.example"
    if env_example.exists():
        shutil.copy2(env_example, repo_root / "dist" / ".env.example")


if __name__ == "__main__":
    main()
