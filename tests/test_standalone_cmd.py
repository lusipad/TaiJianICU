from pathlib import Path

from typer.testing import CliRunner

import cli.standalone_cmd
from cli.main import app
from config.settings import AppSettings


def test_serve_web_uses_windowed_safe_uvicorn_logging(monkeypatch) -> None:
    captured: dict[str, object] = {}

    def fake_run(*args, **kwargs) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(cli.standalone_cmd.uvicorn, "run", fake_run)

    cli.standalone_cmd._serve_web("127.0.0.1", 9130)

    assert captured["args"] == ("webapp.app:create_app",)
    assert captured["kwargs"]["log_config"] is None
    assert captured["kwargs"]["access_log"] is False


def test_standalone_command_starts_local_web_without_browser(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = AppSettings(
        work_dir=tmp_path / "data",
        input_dir=tmp_path / "data" / "input",
        output_dir=tmp_path / "data" / "output",
        sessions_dir=tmp_path / "data" / "sessions",
        lightrag_dir=tmp_path / "data" / "lightrag",
        benchmarks_dir=tmp_path / "data" / "benchmarks",
        web_dir=tmp_path / "data" / "web",
        web_uploads_dir=tmp_path / "data" / "web" / "uploads",
        web_runs_dir=tmp_path / "data" / "web" / "runs",
        web_host="127.0.0.1",
        web_port=9123,
    )
    captured: dict[str, object] = {}

    def fake_serve(host: str, port: int) -> None:
        captured["host"] = host
        captured["port"] = port

    monkeypatch.setattr(cli.standalone_cmd, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.standalone_cmd, "_serve_web", fake_serve)

    result = CliRunner().invoke(app, ["standalone", "--server-only"])

    assert result.exit_code == 0
    assert "TaiJianICU 单机工作台" in result.stdout
    assert "http://127.0.0.1:9123/studio" in result.stdout
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9123


def test_standalone_command_opens_desktop_window(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = AppSettings(
        work_dir=tmp_path / "data",
        input_dir=tmp_path / "data" / "input",
        output_dir=tmp_path / "data" / "output",
        sessions_dir=tmp_path / "data" / "sessions",
        lightrag_dir=tmp_path / "data" / "lightrag",
        benchmarks_dir=tmp_path / "data" / "benchmarks",
        web_dir=tmp_path / "data" / "web",
        web_uploads_dir=tmp_path / "data" / "web" / "uploads",
        web_runs_dir=tmp_path / "data" / "web" / "runs",
        web_host="127.0.0.1",
        web_port=9124,
    )
    captured: dict[str, object] = {}

    class ImmediateThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self) -> None:
            self.target(*self.args)

    def fake_serve(host: str, port: int) -> None:
        captured["served"] = (host, port)

    def fake_window(url: str, health_url: str) -> None:
        captured["window"] = (url, health_url)

    monkeypatch.setattr(cli.standalone_cmd, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.standalone_cmd, "_serve_web", fake_serve)
    monkeypatch.setattr(cli.standalone_cmd, "_run_desktop_window", fake_window)
    monkeypatch.setattr(cli.standalone_cmd.threading, "Thread", ImmediateThread)

    result = CliRunner().invoke(app, ["standalone"])

    assert result.exit_code == 0
    assert captured["served"] == ("127.0.0.1", 9124)
    assert captured["window"] == (
        "http://127.0.0.1:9124/studio",
        "http://127.0.0.1:9124/health",
    )


def test_standalone_command_uses_free_port_when_default_is_busy(
    tmp_path: Path,
    monkeypatch,
) -> None:
    settings = AppSettings(
        work_dir=tmp_path / "data",
        input_dir=tmp_path / "data" / "input",
        output_dir=tmp_path / "data" / "output",
        sessions_dir=tmp_path / "data" / "sessions",
        lightrag_dir=tmp_path / "data" / "lightrag",
        benchmarks_dir=tmp_path / "data" / "benchmarks",
        web_dir=tmp_path / "data" / "web",
        web_uploads_dir=tmp_path / "data" / "web" / "uploads",
        web_runs_dir=tmp_path / "data" / "web" / "runs",
        web_host="127.0.0.1",
        web_port=9125,
    )
    captured: dict[str, object] = {}

    class ImmediateThread:
        def __init__(self, target, args, daemon):
            self.target = target
            self.args = args
            self.daemon = daemon

        def start(self) -> None:
            self.target(*self.args)

    def fake_serve(host: str, port: int) -> None:
        captured["served"] = (host, port)

    def fake_window(url: str, health_url: str) -> None:
        captured["window"] = (url, health_url)

    monkeypatch.setattr(cli.standalone_cmd, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.standalone_cmd, "_is_port_available", lambda host, port: False)
    monkeypatch.setattr(cli.standalone_cmd, "_find_available_port", lambda host: 19125)
    monkeypatch.setattr(cli.standalone_cmd, "_serve_web", fake_serve)
    monkeypatch.setattr(cli.standalone_cmd, "_run_desktop_window", fake_window)
    monkeypatch.setattr(cli.standalone_cmd.threading, "Thread", ImmediateThread)

    result = CliRunner().invoke(app, ["standalone"])

    assert result.exit_code == 0
    assert captured["served"] == ("127.0.0.1", 19125)
    assert captured["window"] == (
        "http://127.0.0.1:19125/studio",
        "http://127.0.0.1:19125/health",
    )
