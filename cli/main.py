from __future__ import annotations

import logging

import typer

from cli.benchmark_cmd import app as benchmark_app
from cli.inspect_cmd import app as inspect_app
from cli.intervene_cmd import app as intervene_app
from cli.run_cmd import app as run_app
from cli.standalone_cmd import app as standalone_app
from cli.web_cmd import app as web_app


logging.getLogger("LiteLLM").setLevel(logging.WARNING)
logging.getLogger("lightrag").setLevel(logging.WARNING)
logging.getLogger("nano-vectordb").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

app = typer.Typer(no_args_is_help=True)
app.add_typer(run_app)
app.add_typer(benchmark_app)
app.add_typer(web_app)
app.add_typer(standalone_app)
app.add_typer(inspect_app)
app.add_typer(intervene_app)


if __name__ == "__main__":
    app()
