from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from config.settings import AppSettings, get_settings
from webapp.errors import ApiError, register_error_handlers
from webapp.manager import WebRunManager
from webapp.models import (
    WebBenchmarkDetail,
    WebBenchmarkSummary,
    WebRunDetail,
    WebRunRequest,
    WebRunSummary,
)


def create_app(
    settings: AppSettings | None = None,
    run_manager: WebRunManager | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    manager = run_manager or WebRunManager(app_settings)
    static_dir = Path(__file__).resolve().parent / "static"

    app = FastAPI(title="TaiJianKiller Web", version="0.1.0")
    app.state.settings = app_settings
    app.state.run_manager = manager

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in app_settings.web_allowed_origins.split(",") if item.strip()],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/api/runs", response_model=list[WebRunSummary])
    async def list_runs() -> list[WebRunSummary]:
        return app.state.run_manager.list_runs()

    @app.get("/api/runs/{run_id}", response_model=WebRunDetail)
    async def get_run(run_id: str) -> WebRunDetail:
        return app.state.run_manager.get_run(run_id)

    @app.get("/api/benchmarks", response_model=list[WebBenchmarkSummary])
    async def list_benchmarks() -> list[WebBenchmarkSummary]:
        return app.state.run_manager.list_benchmarks()

    @app.get("/api/benchmarks/{dataset_name}/{case_name}", response_model=WebBenchmarkDetail)
    async def get_benchmark(dataset_name: str, case_name: str) -> WebBenchmarkDetail:
        return app.state.run_manager.get_benchmark(dataset_name, case_name)

    @app.post("/api/runs", response_model=WebRunSummary, status_code=201)
    async def create_run(
        file: UploadFile = File(...),
        chapters: int = Form(1),
        start_chapter: int = Form(1),
        goal_hint: str = Form(""),
        session_name: str = Form(""),
        planning_mode: str = Form("balanced"),
        new_character_budget: int | None = Form(None),
        new_location_budget: int | None = Form(None),
        new_faction_budget: int | None = Form(None),
        skeleton_candidates: int | None = Form(None),
        draft_candidates: int | None = Form(None),
        use_existing_index: bool = Form(False),
        overwrite: bool = Form(False),
    ) -> WebRunSummary:
        if not file.filename:
            raise ApiError("请上传一个文本文件。", 422, "Invalid Input")
        if not file.filename.lower().endswith(".txt"):
            raise ApiError("当前只支持 .txt 文本文件。", 422, "Invalid Input")
        content = await file.read()
        if not content:
            raise ApiError("上传文件为空。", 422, "Invalid Input")

        input_path, suggested_name = app.state.run_manager.save_uploaded_text(file.filename, content)
        request = WebRunRequest(
            session_name=session_name.strip() or None,
            chapters=chapters,
            start_chapter=start_chapter,
            goal_hint=goal_hint.strip() or None,
            planning_mode=planning_mode,  # pydantic validates enum values
            new_character_budget=new_character_budget,
            new_location_budget=new_location_budget,
            new_faction_budget=new_faction_budget,
            skeleton_candidates=skeleton_candidates,
            draft_candidates=draft_candidates,
            use_existing_index=use_existing_index,
            overwrite=overwrite,
        )
        return app.state.run_manager.start_run(
            input_path=input_path,
            input_filename=file.filename,
            request=request,
        )

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app
