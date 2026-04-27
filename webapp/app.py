from __future__ import annotations

import base64
import secrets
import threading
import time
from pathlib import Path

from fastapi import FastAPI, File, Form, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from config.settings import AppSettings, get_settings
from webapp.errors import ApiError, register_error_handlers
from webapp.manager import WebRunManager
from webapp.models import (
    WebArcSelectionRequest,
    WebBlindChallengeRatingRequest,
    WebExampleDetail,
    WebExampleSummary,
    WebBenchmarkDetail,
    WebBenchmarkSummary,
    WebPublicShowcase,
    WebRuntimeApiOverride,
    WebRuntimeConfig,
    WebRunDetail,
    WebRunRequest,
    WebRunSourceText,
    WebRunSummary,
)

_AUTH_EXEMPT_PATHS = frozenset({"/health", "/ready"})


def _format_window_label(window_seconds: int) -> str:
    if window_seconds % 3600 == 0:
        return f"{window_seconds // 3600} 小时"
    if window_seconds % 60 == 0:
        return f"{window_seconds // 60} 分钟"
    return f"{window_seconds} 秒"


def _client_identifier(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    real_ip = request.headers.get("x-real-ip", "").strip()
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


class _ExampleRunRateLimiter:
    def __init__(self, limit: int, window_seconds: int):
        self.limit = max(0, int(limit))
        self.window_seconds = max(1, int(window_seconds))
        self._lock = threading.Lock()
        self._events: dict[str, list[float]] = {}

    def consume(self, client_id: str) -> None:
        if self.limit <= 0:
            return
        now = time.time()
        cutoff = now - self.window_seconds
        with self._lock:
            events = [stamp for stamp in self._events.get(client_id, []) if stamp > cutoff]
            if len(events) >= self.limit:
                raise ApiError(
                    (
                        f"内置样例试跑次数已用完，请 {_format_window_label(self.window_seconds)} 后再试；"
                        "或者先把样例文本填入上传区，再使用你自己的 endpoint / Key 运行。"
                    ),
                    429,
                    "Too Many Requests",
                )
            events.append(now)
            self._events[client_id] = events


def _unauthorized_response() -> JSONResponse:
    return JSONResponse(
        status_code=401,
        content={"title": "Unauthorized", "status": 401, "detail": "需要认证后才能访问。"},
        headers={"WWW-Authenticate": 'Basic realm="TaiJianICU"'},
    )


def _is_authorized(request: Request, settings: AppSettings) -> bool:
    if not settings.web_password:
        return True
    if request.url.path in _AUTH_EXEMPT_PATHS:
        return True
    auth_header = request.headers.get("authorization", "")
    if not auth_header.startswith("Basic "):
        return False
    encoded = auth_header[6:].strip()
    try:
        decoded = base64.b64decode(encoded).decode("utf-8")
    except Exception:
        return False
    username, separator, password = decoded.partition(":")
    if not separator:
        return False
    return secrets.compare_digest(username, settings.web_username) and secrets.compare_digest(
        password,
        settings.web_password,
    )


def _build_runtime_api_override(
    *,
    api_base_url: str,
    api_key: str,
) -> WebRuntimeApiOverride | None:
    normalized_base_url = api_base_url.strip()
    normalized_api_key = api_key.strip()
    if normalized_base_url and not normalized_base_url.startswith(("http://", "https://")):
        raise ApiError("API endpoint 必须以 http:// 或 https:// 开头。", 422, "Invalid Input")
    if not normalized_base_url and not normalized_api_key:
        return None
    return WebRuntimeApiOverride(
        api_base_url=normalized_base_url or None,
        api_key=normalized_api_key or None,
    )


def create_app(
    settings: AppSettings | None = None,
    run_manager: WebRunManager | None = None,
) -> FastAPI:
    app_settings = settings or get_settings()
    manager = run_manager or WebRunManager(app_settings)
    static_dir = Path(__file__).resolve().parent / "static"

    app = FastAPI(title="TaiJianICU Web", version="0.1.0")
    app.state.settings = app_settings
    app.state.run_manager = manager
    app.state.example_rate_limiter = _ExampleRunRateLimiter(
        app_settings.web_example_runs_per_ip,
        app_settings.web_example_window_seconds,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[item.strip() for item in app_settings.web_allowed_origins.split(",") if item.strip()],
        allow_credentials=True,
        allow_methods=["GET", "POST"],
        allow_headers=["*"],
    )
    register_error_handlers(app)

    @app.middleware("http")
    async def basic_auth_guard(request: Request, call_next):
        if not _is_authorized(request, app.state.settings):
            return _unauthorized_response()
        return await call_next(request)

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

    @app.get("/api/runs/{run_id}/source-text", response_model=WebRunSourceText)
    async def get_run_source_text(run_id: str) -> WebRunSourceText:
        return app.state.run_manager.get_run_source_text(run_id)

    @app.get("/api/benchmarks", response_model=list[WebBenchmarkSummary])
    async def list_benchmarks() -> list[WebBenchmarkSummary]:
        return app.state.run_manager.list_benchmarks()

    @app.get("/api/benchmarks/{dataset_name}/{case_name}", response_model=WebBenchmarkDetail)
    async def get_benchmark(dataset_name: str, case_name: str) -> WebBenchmarkDetail:
        return app.state.run_manager.get_benchmark(dataset_name, case_name)

    @app.get("/api/config", response_model=WebRuntimeConfig)
    async def get_runtime_config() -> WebRuntimeConfig:
        return app.state.run_manager.get_runtime_config()

    @app.get("/api/examples", response_model=list[WebExampleSummary])
    async def list_examples() -> list[WebExampleSummary]:
        return app.state.run_manager.list_examples()

    @app.get("/api/examples/{example_id}", response_model=WebExampleDetail)
    async def get_example(example_id: str) -> WebExampleDetail:
        return app.state.run_manager.get_example(example_id)

    @app.get("/api/showcase", response_model=WebPublicShowcase | None)
    async def get_public_showcase() -> WebPublicShowcase | None:
        return app.state.run_manager.get_public_showcase()

    @app.post("/api/examples/{example_id}/preview-run", response_model=WebRunSummary, status_code=201)
    async def create_example_preview_run(example_id: str) -> WebRunSummary:
        return app.state.run_manager.load_example_preview_run(example_id=example_id)

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
        style_model: str = Form(""),
        plot_model: str = Form(""),
        draft_model: str = Form(""),
        quality_model: str = Form(""),
        lightrag_model_name: str = Form(""),
        api_base_url: str = Form(""),
        api_key: str = Form(""),
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
        runtime_api_override = _build_runtime_api_override(
            api_base_url=api_base_url,
            api_key=api_key,
        )
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
            style_model=style_model.strip() or None,
            plot_model=plot_model.strip() or None,
            draft_model=draft_model.strip() or None,
            quality_model=quality_model.strip() or None,
            lightrag_model_name=lightrag_model_name.strip() or None,
            use_existing_index=use_existing_index,
            overwrite=overwrite,
        )
        return app.state.run_manager.start_run(
            input_path=input_path,
            input_filename=file.filename,
            request=request,
            runtime_api_override=runtime_api_override,
        )

    @app.post("/api/revival/runs", response_model=WebRunSummary, status_code=201)
    async def create_revival_run(
        file: UploadFile = File(...),
        start_chapter: int = Form(1),
        session_name: str = Form(""),
        planning_mode: str = Form("balanced"),
        new_character_budget: int | None = Form(None),
        new_location_budget: int | None = Form(None),
        new_faction_budget: int | None = Form(None),
        style_model: str = Form(""),
        plot_model: str = Form(""),
        draft_model: str = Form(""),
        quality_model: str = Form(""),
        lightrag_model_name: str = Form(""),
        api_base_url: str = Form(""),
        api_key: str = Form(""),
        use_existing_index: bool = Form(False),
    ) -> WebRunSummary:
        if not file.filename:
            raise ApiError("请上传一个文本文件。", 422, "Invalid Input")
        if not file.filename.lower().endswith(".txt"):
            raise ApiError("当前只支持 .txt 文本文件。", 422, "Invalid Input")
        content = await file.read()
        if not content:
            raise ApiError("上传文件为空。", 422, "Invalid Input")
        input_path, _suggested_name = app.state.run_manager.save_uploaded_text(file.filename, content)
        request = WebRunRequest(
            session_name=session_name.strip() or None,
            chapters=1,
            start_chapter=start_chapter,
            planning_mode=planning_mode,  # type: ignore[arg-type]
            new_character_budget=new_character_budget,
            new_location_budget=new_location_budget,
            new_faction_budget=new_faction_budget,
            style_model=style_model.strip() or None,
            plot_model=plot_model.strip() or None,
            draft_model=draft_model.strip() or None,
            quality_model=quality_model.strip() or None,
            lightrag_model_name=lightrag_model_name.strip() or None,
            use_existing_index=use_existing_index,
        )
        runtime_api_override = _build_runtime_api_override(
            api_base_url=api_base_url,
            api_key=api_key,
        )
        return app.state.run_manager.start_revival_analysis_run(
            input_path=input_path,
            input_filename=file.filename,
            request=request,
            runtime_api_override=runtime_api_override,
        )

    @app.post("/api/revival/runs/{run_id}/arc-selection", response_model=WebRunSummary)
    async def select_revival_arc(
        run_id: str,
        request: WebArcSelectionRequest,
    ) -> WebRunSummary:
        return app.state.run_manager.select_revival_arc(run_id, request)

    @app.post("/api/revival/runs/{run_id}/blind-challenge", response_model=WebRunDetail)
    async def save_revival_blind_challenge(
        run_id: str,
        request: WebBlindChallengeRatingRequest,
    ) -> WebRunDetail:
        return app.state.run_manager.save_blind_challenge_rating(run_id, request)

    @app.post("/api/examples/{example_id}/runs", response_model=WebRunSummary, status_code=201)
    async def create_example_run(
        http_request: Request,
        example_id: str,
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
        style_model: str = Form(""),
        plot_model: str = Form(""),
        draft_model: str = Form(""),
        quality_model: str = Form(""),
        lightrag_model_name: str = Form(""),
        api_base_url: str = Form(""),
        api_key: str = Form(""),
        use_existing_index: bool = Form(False),
        overwrite: bool = Form(False),
    ) -> WebRunSummary:
        runtime_api_override = _build_runtime_api_override(
            api_base_url=api_base_url,
            api_key=api_key,
        )
        run_request = WebRunRequest(
            session_name=session_name.strip() or None,
            chapters=chapters,
            start_chapter=start_chapter,
            goal_hint=goal_hint.strip() or None,
            planning_mode=planning_mode,
            new_character_budget=new_character_budget,
            new_location_budget=new_location_budget,
            new_faction_budget=new_faction_budget,
            skeleton_candidates=skeleton_candidates,
            draft_candidates=draft_candidates,
            style_model=style_model.strip() or None,
            plot_model=plot_model.strip() or None,
            draft_model=draft_model.strip() or None,
            quality_model=quality_model.strip() or None,
            lightrag_model_name=lightrag_model_name.strip() or None,
            use_existing_index=use_existing_index,
            overwrite=overwrite,
        )
        uses_server_budget = runtime_api_override is None or not runtime_api_override.api_key
        if uses_server_budget:
            app.state.example_rate_limiter.consume(_client_identifier(http_request))
        return app.state.run_manager.start_example_run(
            example_id=example_id,
            request=run_request,
            runtime_api_override=runtime_api_override,
        )

    @app.get("/", include_in_schema=False)
    async def index() -> FileResponse:
        return FileResponse(static_dir / "landing.html")

    @app.get("/studio", include_in_schema=False)
    async def studio() -> FileResponse:
        return FileResponse(static_dir / "index.html")

    app.mount("/static", StaticFiles(directory=static_dir), name="static")
    return app
