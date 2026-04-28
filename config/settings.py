from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class ModelRoutes(BaseModel):
    plot_model: str = "deepseek/deepseek-chat"
    draft_model: str = "deepseek/deepseek-chat"
    style_model: str = "deepseek/deepseek-chat"
    quality_model: str = "deepseek/deepseek-chat"
    lightrag_model_name: str = "deepseek-chat"
    deepseek_model_name: str = "deepseek-chat"
    deepseek_base_url: str = "https://api.deepseek.com"
    max_tokens: int = 4096
    chapter_max_tokens: int = 6144


class RuntimeTuning(BaseModel):
    rag_query_mode: Literal["local", "global", "hybrid", "naive", "mix", "bypass"] = (
        "mix"
    )
    chunk_size: int = 1800
    chunk_overlap: int = 200
    style_excerpt_chars: int = 12000
    recent_story_excerpt_chars: int = 20000
    consistency_retry_limit: int = 2
    default_scene_count: int = 4
    embedding_backend: Literal["local-hash", "openai"] = "local-hash"
    embedding_dim: int = 384
    embedding_model: str = "text-embedding-3-small"
    top_k: int = 10
    chunk_top_k: int = 5
    quality_threshold: float = 0.65
    quality_retry_limit: int = 1
    skeleton_candidate_count: int = 1
    draft_candidate_count: int = 1
    llm_request_timeout_seconds: float = 180.0
    llm_retry_attempts: int = 4
    llm_retry_backoff_seconds: float = 2.0


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    deepseek_api_key: str | None = Field(default=None, alias="DEEPSEEK_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")
    runtime_api_base_url: str | None = None
    runtime_api_key: str | None = None
    runtime_wire_api: Literal["chat", "responses"] = "chat"

    work_dir: Path = ROOT_DIR / "data"
    input_dir: Path = ROOT_DIR / "data" / "input"
    output_dir: Path = ROOT_DIR / "data" / "output"
    sessions_dir: Path = ROOT_DIR / "data" / "sessions"
    lightrag_dir: Path = ROOT_DIR / "data" / "lightrag"
    benchmarks_dir: Path = ROOT_DIR / "data" / "benchmarks"
    web_dir: Path = ROOT_DIR / "data" / "web"
    web_uploads_dir: Path = ROOT_DIR / "data" / "web" / "uploads"
    web_runs_dir: Path = ROOT_DIR / "data" / "web" / "runs"
    prompts_dir: Path = ROOT_DIR / "config" / "prompts"
    references_dir: Path = ROOT_DIR / "config" / "references"
    web_host: str = "127.0.0.1"
    web_port: int = 8000
    web_username: str = Field(default="admin", alias="TAIJIAN_WEB_USERNAME")
    web_password: str | None = Field(default=None, alias="TAIJIAN_WEB_PASSWORD")
    web_model_options: str = Field(default="", alias="TAIJIAN_WEB_MODEL_OPTIONS")
    web_example_runs_per_ip: int = Field(default=3, alias="TAIJIAN_WEB_EXAMPLE_RUNS_PER_IP")
    web_example_window_seconds: int = Field(default=3600, alias="TAIJIAN_WEB_EXAMPLE_WINDOW_SECONDS")
    web_allowed_origins: str = (
        "http://127.0.0.1:8000,http://localhost:8000,http://127.0.0.1:3000,"
        "http://localhost:3000,http://127.0.0.1:5173,http://localhost:5173"
    )

    models: ModelRoutes = Field(default_factory=ModelRoutes)
    tuning: RuntimeTuning = Field(default_factory=RuntimeTuning)

    @property
    def deepseek_ready(self) -> bool:
        return bool(self.deepseek_api_key)

    def ensure_directories(self) -> None:
        for path in (
            self.work_dir,
            self.input_dir,
            self.output_dir,
            self.sessions_dir,
            self.lightrag_dir,
            self.benchmarks_dir,
            self.web_dir,
            self.web_uploads_dir,
            self.web_runs_dir,
            self.references_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)

    def prompt_path(self, relative_path: str) -> Path:
        return self.prompts_dir / relative_path


@lru_cache(maxsize=1)
def get_settings() -> AppSettings:
    settings = AppSettings()
    settings.models.plot_model = os.getenv("TAIJIAN_PLOT_MODEL", settings.models.plot_model)
    settings.models.draft_model = os.getenv("TAIJIAN_DRAFT_MODEL", settings.models.draft_model)
    settings.models.style_model = os.getenv("TAIJIAN_STYLE_MODEL", settings.models.style_model)
    settings.models.quality_model = os.getenv("TAIJIAN_QUALITY_MODEL", settings.models.quality_model)
    settings.models.lightrag_model_name = os.getenv(
        "TAIJIAN_LIGHTRAG_MODEL",
        settings.models.lightrag_model_name,
    )
    settings.models.deepseek_base_url = os.getenv(
        "DEEPSEEK_BASE_URL",
        settings.models.deepseek_base_url,
    )
    settings.runtime_wire_api = os.getenv(
        "TAIJIAN_WIRE_API",
        settings.runtime_wire_api,
    )
    settings.web_host = os.getenv("TAIJIAN_WEB_HOST", settings.web_host)
    settings.web_port = int(os.getenv("TAIJIAN_WEB_PORT", str(settings.web_port)))
    settings.web_username = os.getenv("TAIJIAN_WEB_USERNAME", settings.web_username)
    settings.web_model_options = os.getenv(
        "TAIJIAN_WEB_MODEL_OPTIONS",
        settings.web_model_options,
    )
    settings.web_allowed_origins = os.getenv(
        "TAIJIAN_WEB_ALLOWED_ORIGINS",
        settings.web_allowed_origins,
    )
    settings.tuning.embedding_backend = os.getenv(
        "TAIJIAN_EMBEDDING_BACKEND",
        settings.tuning.embedding_backend,
    )
    settings.tuning.embedding_model = os.getenv(
        "TAIJIAN_EMBEDDING_MODEL",
        settings.tuning.embedding_model,
    )
    settings.tuning.recent_story_excerpt_chars = int(
        os.getenv(
            "TAIJIAN_RECENT_STORY_EXCERPT_CHARS",
            str(settings.tuning.recent_story_excerpt_chars),
        )
    )
    settings.tuning.rag_query_mode = os.getenv(
        "TAIJIAN_RAG_QUERY_MODE",
        settings.tuning.rag_query_mode,
    )
    settings.tuning.llm_request_timeout_seconds = float(
        os.getenv(
            "TAIJIAN_LLM_TIMEOUT_SECONDS",
            str(settings.tuning.llm_request_timeout_seconds),
        )
    )
    settings.tuning.llm_retry_attempts = int(
        os.getenv(
            "TAIJIAN_LLM_RETRY_ATTEMPTS",
            str(settings.tuning.llm_retry_attempts),
        )
    )
    settings.tuning.llm_retry_backoff_seconds = float(
        os.getenv(
            "TAIJIAN_LLM_RETRY_BACKOFF_SECONDS",
            str(settings.tuning.llm_retry_backoff_seconds),
        )
    )
    settings.tuning.embedding_dim = int(
        os.getenv("TAIJIAN_EMBEDDING_DIM", str(settings.tuning.embedding_dim))
    )
    settings.tuning.skeleton_candidate_count = int(
        os.getenv(
            "TAIJIAN_SKELETON_CANDIDATES",
            str(settings.tuning.skeleton_candidate_count),
        )
    )
    settings.tuning.draft_candidate_count = int(
        os.getenv(
            "TAIJIAN_DRAFT_CANDIDATES",
            str(settings.tuning.draft_candidate_count),
        )
    )
    settings.ensure_directories()
    return settings


@lru_cache(maxsize=32)
def load_prompt(relative_path: str) -> str:
    settings = get_settings()
    return settings.prompt_path(relative_path).read_text(encoding="utf-8")


def render_prompt(relative_path: str, **values: Any) -> str:
    normalized = {
        key: value
        if isinstance(value, str)
        else json.dumps(value, ensure_ascii=False, indent=2)
        for key, value in values.items()
    }
    return load_prompt(relative_path).format(**normalized)
