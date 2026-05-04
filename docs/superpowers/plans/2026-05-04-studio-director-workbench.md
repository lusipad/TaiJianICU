# Studio Director Workbench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Reframe Studio around a multi-chapter director workflow while keeping world, character, statistics, artifacts, and API settings as supporting layers.

**Architecture:** Keep the existing static Studio shell and FastAPI routes. Reorganize navigation, page sections, and client-side rendering so the primary workflow is creation-first: overview, director plan, chapter queue, single-chapter review. Keep library data in supporting resource pages and leave backend persistence unchanged for this slice.

**Tech Stack:** FastAPI static HTML, vanilla JavaScript, CSS, pytest with FastAPI TestClient.

---

### Task 1: Lock the Studio Information Architecture

**Files:**
- Modify: `tests/test_web_app.py`
- Modify: `webapp/static/index.html`
- Modify: `webapp/static/app.js`

- [ ] **Step 1: Write failing route and label expectations**

Add assertions that `/studio` contains `data-studio-page-link="overview"`, `data-studio-page-link="director"`, `data-studio-page-link="chapters"`, `data-studio-page-link="review"`, `data-studio-page-link="world"`, `data-studio-page-link="characters"`, `data-studio-page-link="threads"`, `data-studio-page-link="stats"`, `data-studio-page-link="artifacts"`, and `data-studio-page-link="settings"`.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_web_app.py::test_studio_pages_are_split_by_route -q`

Expected: FAIL because the new route markers do not exist yet.

- [ ] **Step 3: Update HTML navigation**

Replace the flat sidebar with grouped sections: `创作区`, `资料库`, and `运行配置`. Add route markers for the new Studio pages and keep links served by the existing `/studio/{studio_page}` route.

- [ ] **Step 4: Update page routing map**

Update `studioPages` and `studioPathPages` in `webapp/static/app.js` so `/studio` maps to `overview`, and new routes map to their expected page keys.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_web_app.py::test_studio_pages_are_split_by_route -q`

Expected: PASS.

### Task 2: Promote Director Workflow Sections

**Files:**
- Modify: `tests/test_web_app.py`
- Modify: `webapp/static/index.html`
- Modify: `webapp/static/app.js`
- Modify: `webapp/static/studio.css`

- [ ] **Step 1: Write failing content assertions**

Assert that the Studio page contains `阶段导演计划`, `章节队列`, `单章评审`, `资料库`, `API 配置`, and `连接测试`.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_web_app.py::test_web_health_and_index -q`

Expected: FAIL before the new labels and sections exist.

- [ ] **Step 3: Reorganize run view**

Keep the existing output preview and diagnostics data, but expose it through four creation sections: overview, director plan, chapter queue, and review. Move world, character, thread, stats, artifacts, and settings into page sections that behave like supporting views.

- [ ] **Step 4: Update visibility logic**

Ensure `data-page-section` values match the new route keys and that tabs no longer masquerade as the primary product navigation.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_web_app.py::test_web_health_and_index -q`

Expected: PASS.

### Task 3: Fix Markdown Preview Coverage

**Files:**
- Modify: `tests/test_web_app.py`
- Modify: `webapp/static/app.js`
- Modify: `webapp/static/studio.css`

- [ ] **Step 1: Write a static assertion for Markdown support**

Assert `renderMarkdownPreview` supports fenced code blocks and nested-looking block content by checking for code fence handling markers in `app.js`.

- [ ] **Step 2: Run the focused test and verify RED**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_web_app.py::test_studio_static_scripts_support_markdown_preview -q`

Expected: FAIL because fenced code block rendering is not implemented.

- [ ] **Step 3: Extend the small renderer**

Add minimal fenced code block support without adding dependencies. Keep escaping centralized through `escapeHtml`.

- [ ] **Step 4: Style code blocks**

Add `.markdown-preview pre` styling so generated reports and notes remain readable.

- [ ] **Step 5: Run the focused test and verify GREEN**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_web_app.py::test_studio_static_scripts_support_markdown_preview -q`

Expected: PASS.

### Task 4: Final Verification

**Files:**
- Modify: `tests/test_web_app.py`
- Modify: `webapp/static/index.html`
- Modify: `webapp/static/app.js`
- Modify: `webapp/static/studio.css`

- [ ] **Step 1: Run focused web tests**

Run: `.\.venv\Scripts\python.exe -m pytest tests/test_web_app.py -q`

Expected: PASS.

- [ ] **Step 2: Run full test suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q`

Expected: PASS.

- [ ] **Step 3: Review diff**

Run: `git diff -- webapp/static/index.html webapp/static/app.js webapp/static/studio.css tests/test_web_app.py docs/superpowers/plans/2026-05-04-studio-director-workbench.md`

Expected: Diff only contains Studio IA, presentation, markdown, tests, and plan changes.
