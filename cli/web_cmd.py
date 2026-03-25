from __future__ import annotations

import typer
import uvicorn

from config.settings import get_settings


app = typer.Typer(help="启动 Web 前端与 API 服务")


@app.command("web")
def web_command(
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
) -> None:
    settings = get_settings()
    uvicorn.run(
        "webapp.app:create_app",
        factory=True,
        host=host or settings.web_host,
        port=port or settings.web_port,
        reload=False,
    )
