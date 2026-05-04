from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from fastapi.testclient import TestClient

from config.settings import AppSettings
from webapp.app import create_app
from webapp.models import (
    WebExampleDetail,
    WebBenchmarkDetail,
    WebExampleSummary,
    WebPublicShowcase,
    WebArcSelectionRequest,
    WebBlindChallengeRatingRequest,
    WebRuntimeApiOverride,
    WebRunDetail,
    WebRunProgress,
    WebRunRequest,
    WebRunSourceText,
    WebRunSummary,
)


class FakeRunManager:
    def __init__(self):
        now = datetime.now(timezone.utc)
        self.detail = WebRunDetail(
            id="run-1",
            status="completed",
            created_at=now,
            updated_at=now,
            session_name="demo-session",
            input_filename="demo.txt",
            request=WebRunRequest(chapters=1, start_chapter=1),
            progress=WebRunProgress(total_steps=5, completed_steps=5, message="运行完成"),
            log_messages=["阶段1：索引与风格分析", "运行完成"],
            input_path="demo.txt",
            output_paths=["chapter_1.md"],
            latest_source_preview_label="原文断点",
            latest_source_preview="示例原文",
            latest_output_preview="示例正文",
        )
        self.start_calls = 0
        self.revival_start_calls = 0
        self.arc_selection_calls = 0
        self.blind_rating_calls = 0
        self.preview_calls = 0
        self.last_request = None
        self.last_runtime_api_override = None

    def list_runs(self):
        return [WebRunSummary.model_validate(self.detail.model_dump(mode="json"))]

    def get_runtime_config(self):
        return {
            "style_model": "deepseek/deepseek-chat",
            "plot_model": "deepseek/deepseek-chat",
            "draft_model": "deepseek/deepseek-chat",
            "quality_model": "deepseek/deepseek-chat",
            "lightrag_model_name": "deepseek-chat",
            "api_base_url": "https://api.deepseek.com",
            "wire_api": "chat",
            "model_options": [
                "deepseek/deepseek-chat",
                "deepseek/deepseek-reasoner",
                "openai/gpt-4.1-mini",
            ],
        }

    def list_benchmarks(self):
        return [
            {
                "dataset_name": "demo",
                "case_name": "1_to_2",
                "target_chapter_number": 2,
                "prefix_chapter_count": 1,
                "winner": "system",
                "confidence": 0.9,
                "report_json_path": "benchmark_report.json",
                "report_markdown_path": "benchmark_report.md",
            }
        ]

    def list_examples(self):
        return [
            WebExampleSummary(
                id="sample_novel",
                title="原创悬疑样例",
                description="仓库内原创短篇样例，首次打开就能试跑，不依赖你先上传文件。",
                input_filename="sample_novel.txt",
                recommended_goal_hint="先推进主角与尾随者的正面碰撞，再回收一个旧伏笔。",
                source_excerpt="第一章 雨夜追魂",
                usage_hint="可以先快速试看预计算结果；如果要测试当前 endpoint / Key 和模型配置，再按当前配置重跑。",
                trial_limit_note="快速试看不消耗额度；按当前配置重跑在使用部署默认 Key 时按单 IP 限流。",
            )
        ]

    def get_example(self, example_id: str):
        assert example_id == "sample_novel"
        return WebExampleDetail(
            id="sample_novel",
            title="原创悬疑样例",
            description="仓库内原创短篇样例，首次打开就能试跑，不依赖你先上传文件。",
            input_filename="sample_novel.txt",
            recommended_goal_hint="先推进主角与尾随者的正面碰撞，再回收一个旧伏笔。",
            source_excerpt="第一章 雨夜追魂",
            usage_hint="可以先快速试看预计算结果；如果要测试当前 endpoint / Key 和模型配置，再按当前配置重跑。",
            trial_limit_note="快速试看不消耗额度；按当前配置重跑在使用部署默认 Key 时按单 IP 限流。",
            text_content="第一章 雨夜追魂\n\n沈照站在义庄门口。",
        )

    def load_example_preview_run(self, *, example_id: str):
        assert example_id == "sample_novel"
        self.preview_calls += 1
        preview_detail = self.detail.model_copy(
            update={
                "id": "example-preview-sample_novel",
                "session_name": "sample_novel-demo",
                "request": self.detail.request.model_copy(update={"use_existing_index": True}),
                "progress": self.detail.progress.model_copy(update={"message": "已加载预计算样例结果"}),
            }
        )
        return WebRunSummary.model_validate(preview_detail.model_dump(mode="json"))

    def get_public_showcase(self):
        return WebPublicShowcase(
            title="红楼梦第120回 · source-voice 回归",
            source_label="红楼梦前80回断点 · 公版原文片段",
            source_excerpt="迎春方哭哭啼啼的在王夫人房中诉委曲。",
            output_label="红楼梦第120回 · AI 续写片段",
            output_excerpt="话说宝玉自晴雯去后，终日恍恍惚惚。",
            chapter_goal="承接迎春归宁受苦与大观园离散，推进第120回末段声口验证。",
            evaluation_summary="推进稳定。",
            continuity_score=0.9,
            character_score=0.48,
            world_consistency_score=0.9,
            novelty_score=0.8,
            arc_progress_score=0.95,
        )

    def get_benchmark(self, dataset_name: str, case_name: str):
        assert dataset_name == "demo"
        assert case_name == "1_to_2"
        return WebBenchmarkDetail(
            dataset_name="demo",
            case_name="1_to_2",
            target_chapter_number=2,
            prefix_chapter_count=1,
            winner="system",
            confidence=0.9,
            report_json_path="benchmark_report.json",
            report_markdown_path="benchmark_report.md",
            system_output_path="system.md",
            baseline_output_path="baseline.md",
            reference_path="reference.md",
            pairwise_reasoning=["更稳"],
            system_score=0.85,
            baseline_score=0.6,
            system_summary="更稳",
            baseline_summary="一般",
            system_strengths=["剧情推进稳"],
            baseline_strengths=["语言顺"],
            system_weaknesses=["爆点稍弱"],
            baseline_weaknesses=["偏离原著"],
            system_elapsed_seconds=12.3,
            baseline_elapsed_seconds=8.4,
            total_cost_usd=0.12,
            total_tokens=1234,
        )

    def get_run(self, run_id: str):
        assert run_id == "run-1"
        return self.detail

    def get_run_source_text(self, run_id: str):
        assert run_id == "run-1"
        return WebRunSourceText(
            input_filename="demo.txt",
            text_content="第一章 雨夜追魂\n\n沈照站在义庄门口。",
            character_count=18,
        )

    def save_uploaded_text(self, filename: str, content: bytes):
        return Path("demo.txt"), "demo"

    def start_run(
        self,
        *,
        input_path: Path,
        input_filename: str,
        request: WebRunRequest,
        runtime_api_override: WebRuntimeApiOverride | None = None,
    ):
        self.start_calls += 1
        self.last_request = request
        self.last_runtime_api_override = runtime_api_override
        return WebRunSummary.model_validate(self.detail.model_dump(mode="json"))

    def start_revival_analysis_run(
        self,
        *,
        input_path: Path,
        input_filename: str,
        request: WebRunRequest,
        runtime_api_override: WebRuntimeApiOverride | None = None,
    ):
        self.revival_start_calls += 1
        self.last_request = request
        self.last_runtime_api_override = runtime_api_override
        revival_detail = self.detail.model_copy(
            update={
                "status": "queued",
                "request": request,
            }
        )
        return WebRunSummary.model_validate(revival_detail.model_dump(mode="json"))

    def select_revival_arc(self, run_id: str, request: WebArcSelectionRequest):
        assert run_id == "run-1"
        self.arc_selection_calls += 1
        self.last_request = request
        return WebRunSummary.model_validate(
            self.detail.model_copy(update={"status": "generating"}).model_dump(mode="json")
        )

    def save_blind_challenge_rating(self, run_id: str, request: WebBlindChallengeRatingRequest):
        assert run_id == "run-1"
        self.blind_rating_calls += 1
        self.last_request = request
        return self.detail

    def start_example_run(
        self,
        *,
        example_id: str,
        request: WebRunRequest,
        runtime_api_override: WebRuntimeApiOverride | None = None,
    ):
        assert example_id == "sample_novel"
        self.start_calls += 1
        self.last_request = request
        self.last_runtime_api_override = runtime_api_override
        return WebRunSummary.model_validate(self.detail.model_dump(mode="json"))


def test_web_health_and_index() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").json() == {"status": "ok"}
    response = client.get("/")
    assert response.status_code == 200
    assert "TaiJianICU" in response.text
    assert "让<span>故事</span>" in response.text
    assert "开始免费试用" in response.text
    assert "红楼梦第120回" not in response.text
    studio = client.get("/studio")
    assert studio.status_code == 200
    assert "TaiJianICU Studio" in studio.text
    assert "世界设定" in studio.text
    assert "AI 生成的续写章节" in studio.text
    assert "拼接预览" in studio.text
    assert "导演人物走向" in studio.text
    assert "盲看 1000 字" in studio.text
    assert "studio-overview.png" not in studio.text
    assert "第一次用？先免费试看，再决定要不要真跑" in studio.text
    assert "按当前配置试跑样例" in studio.text
    assert "使用自己的 Key，或者直接用本地版本" in studio.text
    favicon = client.get("/static/favicon.svg")
    assert favicon.status_code == 200
    assert "image/svg+xml" in favicon.headers["content-type"]


def test_studio_pages_are_split_by_route() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    expected_pages = {
        "/studio": "data-studio-page-link=\"dashboard\"",
        "/studio/library": "data-studio-page-link=\"library\"",
        "/studio/world": "data-studio-page-link=\"world\"",
        "/studio/characters": "data-studio-page-link=\"characters\"",
        "/studio/stats": "data-studio-page-link=\"stats\"",
        "/studio/settings": "data-studio-page-link=\"settings\"",
    }

    for path, marker in expected_pages.items():
        response = client.get(path)
        assert response.status_code == 200
        assert marker in response.text

    assert client.get("/studio/missing").status_code == 404


def test_marketing_pages_are_split_by_route() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    expected_pages = {
        "/product": "专注长期创作的",
        "/showcase": "红楼梦第120回",
        "/docs": "文档中心",
        "/about": "让你的故事，在你掌控下延续。",
    }

    for path, title in expected_pages.items():
        response = client.get(path)
        assert response.status_code == 200
        assert title in response.text
        assert "browser-chrome" not in response.text
        assert "/pricing" not in response.text
        assert "/studio#quickstart-sample" not in response.text
        assert "定价" not in response.text

    assert client.get("/pricing").status_code == 404


def test_web_requires_basic_auth_when_password_configured() -> None:
    settings = AppSettings(TAIJIAN_WEB_PASSWORD="secret123")
    app = create_app(settings=settings, run_manager=FakeRunManager())
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    index_response = client.get("/")
    assert index_response.status_code == 401
    assert "Basic" in index_response.headers["www-authenticate"]

    authed_response = client.get("/", auth=("admin", "secret123"))
    assert authed_response.status_code == 200
    assert "开始免费试用" in authed_response.text

    product_response = client.get("/product", auth=("admin", "secret123"))
    assert product_response.status_code == 200
    assert "专注长期创作的" in product_response.text

    studio_response = client.get("/studio", auth=("admin", "secret123"))
    assert studio_response.status_code == 200
    assert "TaiJianICU Studio" in studio_response.text


def test_api_requires_basic_auth_when_password_configured() -> None:
    settings = AppSettings(TAIJIAN_WEB_PASSWORD="secret123")
    app = create_app(settings=settings, run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/runs")
    assert response.status_code == 401

    authed = client.get("/api/runs", auth=("admin", "secret123"))
    assert authed.status_code == 200
    assert authed.json()[0]["id"] == "run-1"


def test_create_run_rejects_non_txt_upload() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        files={"file": ("demo.md", b"# nope", "text/markdown")},
        data={"chapters": "1", "start_chapter": "1"},
    )

    assert response.status_code == 422
    assert "txt" in response.json()["detail"]


def test_create_run_accepts_txt_upload() -> None:
    manager = FakeRunManager()
    app = create_app(settings=AppSettings(), run_manager=manager)
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        files={"file": ("demo.txt", "第一章 测试".encode("utf-8"), "text/plain")},
        data={
            "chapters": "1",
            "start_chapter": "1",
            "planning_mode": "expansive",
            "new_character_budget": "2",
            "new_location_budget": "1",
            "new_faction_budget": "1",
            "skeleton_candidates": "2",
            "draft_candidates": "3",
            "style_model": "openai/gpt-4.1-mini",
            "plot_model": "openai/gpt-4.1-mini",
            "draft_model": "deepseek/deepseek-chat",
            "quality_model": "deepseek/deepseek-chat",
            "lightrag_model_name": "openai/gpt-4.1-mini",
            "api_base_url": "https://openrouter.ai/api/v1",
            "api_key": "sk-demo",
            "wire_api": "responses",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == "run-1"
    assert response.json()["progress"]["percent"] == 100.0
    assert response.json()["progress"]["completed_label"] == "5/5"
    assert manager.start_calls == 1
    assert manager.last_request.planning_mode == "expansive"
    assert manager.last_request.new_character_budget == 2
    assert manager.last_request.new_location_budget == 1
    assert manager.last_request.new_faction_budget == 1
    assert manager.last_request.skeleton_candidates == 2
    assert manager.last_request.draft_candidates == 3
    assert manager.last_request.style_model == "openai/gpt-4.1-mini"
    assert manager.last_request.plot_model == "openai/gpt-4.1-mini"
    assert manager.last_request.lightrag_model_name == "openai/gpt-4.1-mini"
    assert manager.last_runtime_api_override == WebRuntimeApiOverride(
        api_base_url="https://openrouter.ai/api/v1",
        api_key="sk-demo",
        wire_api="responses",
    )


def test_create_revival_run_accepts_txt_upload() -> None:
    manager = FakeRunManager()
    app = create_app(settings=AppSettings(), run_manager=manager)
    client = TestClient(app)

    response = client.post(
        "/api/revival/runs",
        files={"file": ("demo.txt", "第一章 测试".encode("utf-8"), "text/plain")},
        data={
            "start_chapter": "1",
            "planning_mode": "balanced",
            "api_base_url": "https://openrouter.ai/api/v1",
            "api_key": "sk-demo",
            "wire_api": "responses",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == "run-1"
    assert manager.revival_start_calls == 1
    assert manager.last_request.chapters == 1
    assert manager.last_runtime_api_override == WebRuntimeApiOverride(
        api_base_url="https://openrouter.ai/api/v1",
        api_key="sk-demo",
        wire_api="responses",
    )


def test_revival_arc_selection_endpoint() -> None:
    manager = FakeRunManager()
    app = create_app(settings=AppSettings(), run_manager=manager)
    client = TestClient(app)

    response = client.post(
        "/api/revival/runs/run-1/arc-selection",
        json={"selected_option_id": "arc_a", "arc_options_digest": "digest", "user_note": "稳住节奏"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "generating"
    assert manager.arc_selection_calls == 1
    assert manager.last_request.selected_option_id == "arc_a"


def test_revival_blind_challenge_endpoint() -> None:
    manager = FakeRunManager()
    app = create_app(settings=AppSettings(), run_manager=manager)
    client = TestClient(app)

    response = client.post(
        "/api/revival/runs/run-1/blind-challenge",
        json={
            "voice_match_score": 5,
            "rhythm_match_score": 4,
            "character_voice_score": 5,
            "notes": "像",
        },
    )

    assert response.status_code == 200
    assert response.json()["id"] == "run-1"
    assert manager.blind_rating_calls == 1
    assert manager.last_request.voice_match_score == 5


def test_get_runtime_config_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/config")

    assert response.status_code == 200
    assert response.json()["style_model"] == "deepseek/deepseek-chat"
    assert response.json()["api_base_url"] == "https://api.deepseek.com"
    assert response.json()["wire_api"] == "chat"
    assert "openai/gpt-4.1-mini" in response.json()["model_options"]


def test_list_examples_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/examples")

    assert response.status_code == 200
    assert response.json()[0]["id"] == "sample_novel"


def test_get_public_showcase_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/showcase")

    assert response.status_code == 200
    assert response.json()["title"] == "红楼梦第120回 · source-voice 回归"
    assert response.json()["source_label"] == "红楼梦前80回断点 · 公版原文片段"


def test_get_example_detail_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/examples/sample_novel")

    assert response.status_code == 200
    assert response.json()["input_filename"] == "sample_novel.txt"
    assert "沈照" in response.json()["text_content"]


def test_create_example_preview_run_endpoint() -> None:
    manager = FakeRunManager()
    app = create_app(settings=AppSettings(), run_manager=manager)
    client = TestClient(app)

    response = client.post("/api/examples/sample_novel/preview-run")

    assert response.status_code == 201
    assert response.json()["id"] == "example-preview-sample_novel"
    assert response.json()["request"]["use_existing_index"] is True
    assert manager.preview_calls == 1


def test_get_run_endpoint_includes_source_preview() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/runs/run-1")

    assert response.status_code == 200
    assert response.json()["latest_source_preview_label"] == "原文断点"
    assert response.json()["latest_source_preview"] == "示例原文"


def test_get_run_source_text_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/runs/run-1/source-text")

    assert response.status_code == 200
    assert response.json()["input_filename"] == "demo.txt"
    assert "沈照站在义庄门口" in response.json()["text_content"]


def test_create_example_run_endpoint() -> None:
    manager = FakeRunManager()
    app = create_app(settings=AppSettings(), run_manager=manager)
    client = TestClient(app)

    response = client.post(
        "/api/examples/sample_novel/runs",
        data={
            "chapters": "1",
            "start_chapter": "1",
            "draft_model": "deepseek/deepseek-chat",
            "api_base_url": "https://openrouter.ai/api/v1",
            "api_key": "sk-demo",
            "wire_api": "responses",
        },
    )

    assert response.status_code == 201
    assert response.json()["id"] == "run-1"
    assert manager.start_calls == 1
    assert manager.last_request.draft_model == "deepseek/deepseek-chat"
    assert manager.last_runtime_api_override == WebRuntimeApiOverride(
        api_base_url="https://openrouter.ai/api/v1",
        api_key="sk-demo",
        wire_api="responses",
    )


def test_create_example_run_rate_limited_by_ip() -> None:
    manager = FakeRunManager()
    settings = AppSettings(
        TAIJIAN_WEB_EXAMPLE_RUNS_PER_IP=1,
        TAIJIAN_WEB_EXAMPLE_WINDOW_SECONDS=3600,
    )
    app = create_app(settings=settings, run_manager=manager)
    client = TestClient(app)

    first = client.post("/api/examples/sample_novel/runs", data={"chapters": "1", "start_chapter": "1"})
    second = client.post("/api/examples/sample_novel/runs", data={"chapters": "1", "start_chapter": "1"})

    assert first.status_code == 201
    assert second.status_code == 429
    assert "endpoint / Key" in second.json()["detail"]


def test_create_example_run_with_custom_key_bypasses_trial_rate_limit() -> None:
    manager = FakeRunManager()
    settings = AppSettings(
        TAIJIAN_WEB_EXAMPLE_RUNS_PER_IP=1,
        TAIJIAN_WEB_EXAMPLE_WINDOW_SECONDS=3600,
    )
    app = create_app(settings=settings, run_manager=manager)
    client = TestClient(app)

    first = client.post(
        "/api/examples/sample_novel/runs",
        data={"chapters": "1", "start_chapter": "1", "api_key": "sk-user"},
    )
    second = client.post(
        "/api/examples/sample_novel/runs",
        data={"chapters": "1", "start_chapter": "1", "api_key": "sk-user"},
    )

    assert first.status_code == 201
    assert second.status_code == 201


def test_create_run_rejects_invalid_api_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        files={"file": ("demo.txt", "第一章 测试".encode("utf-8"), "text/plain")},
        data={
            "chapters": "1",
            "start_chapter": "1",
            "api_base_url": "not-a-url",
        },
    )

    assert response.status_code == 422
    assert "endpoint" in response.json()["detail"]


def test_create_run_rejects_invalid_wire_api() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.post(
        "/api/runs",
        files={"file": ("demo.txt", "第一章 测试".encode("utf-8"), "text/plain")},
        data={
            "chapters": "1",
            "start_chapter": "1",
            "wire_api": "assistants",
        },
    )

    assert response.status_code == 422
    assert "Wire API" in response.json()["detail"]


def test_list_benchmarks_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/benchmarks")

    assert response.status_code == 200
    assert response.json()[0]["dataset_name"] == "demo"


def test_get_benchmark_endpoint() -> None:
    app = create_app(settings=AppSettings(), run_manager=FakeRunManager())
    client = TestClient(app)

    response = client.get("/api/benchmarks/demo/1_to_2")

    assert response.status_code == 200
    assert response.json()["system_summary"] == "更稳"
