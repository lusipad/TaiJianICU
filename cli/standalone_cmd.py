from __future__ import annotations

import socket
import threading
import time
import traceback
import urllib.request

import typer
import uvicorn
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtWidgets import QApplication, QMainWindow
from PySide6.QtWebEngineWidgets import QWebEngineView

from config.settings import get_settings


app = typer.Typer(help="启动单机 Web 工作台")


def _append_standalone_log(message: str) -> None:
    try:
        settings = get_settings()
        log_path = settings.work_dir / "TaiJianICU.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as file:
            file.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')} {message}\n")
    except Exception:
        pass


def _is_port_available(host: str, port: int) -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind((host, port))
            return True
    except OSError:
        return False


def _find_available_port(host: str) -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((host, 0))
        return int(sock.getsockname()[1])


def _resolve_standalone_port(host: str, configured_port: int, explicit_port: int | None) -> int:
    if explicit_port is not None:
        return explicit_port
    if _is_port_available(host, configured_port):
        return configured_port
    resolved_port = _find_available_port(host)
    _append_standalone_log(
        f"configured port {configured_port} is busy; using {resolved_port}",
    )
    return resolved_port


def _wait_for_health(health_url: str, timeout_seconds: float = 45.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(health_url, timeout=0.5) as response:
                body = response.read().decode("utf-8", errors="replace")
            if response.status == 200 and '"status":"ok"' in body.replace(" ", ""):
                return True
        except Exception:
            time.sleep(0.2)
    return False


def _serve_web(host: str, port: int) -> None:
    _append_standalone_log(f"starting internal server http://{host}:{port}")
    try:
        uvicorn.run(
            "webapp.app:create_app",
            factory=True,
            host=host,
            port=port,
            reload=False,
            log_config=None,
            log_level="warning",
            access_log=False,
        )
    except Exception as exc:
        _append_standalone_log(f"internal server failed: {exc}")
        _append_standalone_log(traceback.format_exc())
        raise


def _run_desktop_window(url: str, health_url: str) -> None:
    app = QApplication([])
    window = QMainWindow()
    window.setWindowTitle("TaiJianICU")
    window.resize(1440, 960)

    view = QWebEngineView()
    view.setHtml(
        """
        <!doctype html>
        <html lang="zh-CN">
          <head>
            <meta charset="utf-8">
            <style>
              body {
                margin: 0;
                min-height: 100vh;
                display: grid;
                place-items: center;
                font-family: "Microsoft YaHei", "Segoe UI", sans-serif;
                color: #172033;
                background: #f5f1e8;
              }
              main { text-align: center; }
              h1 { margin: 0 0 12px; font-size: 28px; font-weight: 650; }
              p { margin: 0; color: #667085; font-size: 15px; }
            </style>
          </head>
          <body>
            <main>
              <h1>TaiJianICU 正在启动</h1>
              <p>首次启动会解压内置运行环境，请稍等片刻。</p>
            </main>
          </body>
        </html>
        """,
    )
    window.setCentralWidget(view)
    window.show()

    started_waiting = time.monotonic()

    def load_when_ready() -> None:
        if _wait_for_health(health_url, timeout_seconds=0.2):
            _append_standalone_log(f"loading desktop window {url}")
            view.setUrl(QUrl(url))
            ready_timer.stop()
        elif time.monotonic() - started_waiting > 180.0:
            _append_standalone_log("internal server readiness timed out")
            view.setHtml("<h1>TaiJianICU 启动超时</h1><p>请关闭窗口后重试。</p>")
            ready_timer.stop()

    ready_timer = QTimer()
    ready_timer.timeout.connect(load_when_ready)
    ready_timer.start(500)
    app.exec()


@app.command("standalone")
def standalone_command(
    host: str | None = typer.Option(None, "--host"),
    port: int | None = typer.Option(None, "--port"),
    server_only: bool = typer.Option(False, "--server-only"),
) -> None:
    settings = get_settings()
    resolved_host = host or settings.web_host
    resolved_port = _resolve_standalone_port(resolved_host, settings.web_port, port)
    url = f"http://{resolved_host}:{resolved_port}/studio"
    health_url = f"http://{resolved_host}:{resolved_port}/health"

    typer.echo("TaiJianICU 单机工作台")
    typer.echo(f"数据目录：{settings.work_dir}")
    typer.echo(f"内部地址：{url}")
    _append_standalone_log(f"standalone command started, url={url}")

    if server_only:
        typer.echo("服务模式启动，关闭此窗口即可停止服务。")
        _serve_web(resolved_host, resolved_port)
        return

    typer.echo("正在打开应用窗口。")
    threading.Thread(
        target=_serve_web,
        args=(resolved_host, resolved_port),
        daemon=True,
    ).start()

    try:
        _run_desktop_window(url, health_url)
    except Exception as exc:
        _append_standalone_log(f"desktop window failed: {exc}")
        _append_standalone_log(traceback.format_exc())
        typer.echo(f"桌面窗口启动失败：{exc}", err=True)
        typer.echo("已退回服务模式，可在本机浏览器打开上面的内部地址。", err=True)
        while True:
            time.sleep(3600)
