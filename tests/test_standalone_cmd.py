from pathlib import Path

from typer.testing import CliRunner

import cli.standalone_cmd
from cli.main import app
from config.settings import AppSettings


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

    def fake_run(app_path: str, **kwargs) -> None:
        captured["app_path"] = app_path
        captured.update(kwargs)

    monkeypatch.setattr(cli.standalone_cmd, "get_settings", lambda: settings)
    monkeypatch.setattr(cli.standalone_cmd.uvicorn, "run", fake_run)

    result = CliRunner().invoke(app, ["standalone", "--no-open-browser"])

    assert result.exit_code == 0
    assert "TaiJianICU 单机工作台" in result.stdout
    assert "http://127.0.0.1:9123/studio" in result.stdout
    assert captured["app_path"] == "webapp.app:create_app"
    assert captured["factory"] is True
    assert captured["host"] == "127.0.0.1"
    assert captured["port"] == 9123

