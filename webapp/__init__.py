from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from config.settings import AppSettings
    from webapp.manager import WebRunManager


def create_app(
    settings: "AppSettings | None" = None,
    run_manager: "WebRunManager | None" = None,
) -> "FastAPI":
    from webapp.app import create_app as _create_app

    return _create_app(settings=settings, run_manager=run_manager)


__all__ = ["create_app"]
