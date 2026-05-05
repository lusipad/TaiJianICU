from __future__ import annotations

import socket
import threading
import time
import webbrowser

import typer
import uvicorn

from config.settings import get_settings


app = typer.Typer(help="启动单机 Web 工作台")


def _wait_for_port(host: str, port: int, timeout_seconds: float = 15.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                return True
        except OSError:
            time.sleep(0.2)
    return False


def _open_browser_when_ready(url: str, host: str, port: int) -> None:
    if _wait_for_port(host, port):
        webbrowser.open(url)


@app.command("standalone")
def standalone_command(
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
    open_browser: bool = typer.Option(True, "--open-browser/--no-open-browser"),
) -> None:
    settings = get_settings()
    resolved_host = host or settings.web_host
    resolved_port = port or settings.web_port
    url = f"http://{resolved_host}:{resolved_port}/studio"

    typer.echo("TaiJianICU 单机工作台")
    typer.echo(f"数据目录：{settings.work_dir}")
    typer.echo(f"访问地址：{url}")
    typer.echo("关闭此窗口即可停止服务。")

    if open_browser:
        threading.Thread(
            target=_open_browser_when_ready,
            args=(url, resolved_host, resolved_port),
            daemon=True,
        ).start()

    uvicorn.run(
        "webapp.app:create_app",
        factory=True,
        host=resolved_host,
        port=resolved_port,
        reload=False,
    )

