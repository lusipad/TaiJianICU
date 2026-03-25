const state = {
  activeRunId: null,
  pollTimer: null,
  runCache: [],
};

const elements = {
  form: document.getElementById("run-form"),
  submitButton: document.getElementById("submit-button"),
  formStatus: document.getElementById("form-status"),
  fileInput: document.getElementById("file-input"),
  selectedFileName: document.getElementById("selected-file-name"),
  runList: document.getElementById("run-list"),
  emptyState: document.getElementById("empty-state"),
  runView: document.getElementById("run-view"),
  errorBanner: document.getElementById("error-banner"),
  runId: document.getElementById("run-id"),
  runSession: document.getElementById("run-session"),
  runStatus: document.getElementById("run-status"),
  progressFill: document.getElementById("progress-fill"),
  progressMessage: document.getElementById("progress-message"),
  progressPercent: document.getElementById("progress-percent"),
  progressCount: document.getElementById("progress-count"),
  metricCalls: document.getElementById("metric-calls"),
  metricTokens: document.getElementById("metric-tokens"),
  metricCost: document.getElementById("metric-cost"),
  metricChapters: document.getElementById("metric-chapters"),
  metricQuality: document.getElementById("metric-quality"),
  metricConsistency: document.getElementById("metric-consistency"),
  styleSummary: document.getElementById("style-summary"),
  storySummary: document.getElementById("story-summary"),
  goalSummary: document.getElementById("goal-summary"),
  artifactList: document.getElementById("artifact-list"),
  qualitySummary: document.getElementById("quality-summary"),
  consistencySummary: document.getElementById("consistency-summary"),
  threadsList: document.getElementById("threads-list"),
  chapterList: document.getElementById("chapter-list"),
  outputPath: document.getElementById("output-path"),
  outputPreview: document.getElementById("output-preview"),
  runLogs: document.getElementById("run-logs"),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(Number(value || 0));
}

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(6)}`;
}

function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "-";
  const totalSeconds = Math.max(0, Math.round(Number(seconds)));
  const minutes = Math.floor(totalSeconds / 60);
  const remain = totalSeconds % 60;
  if (!minutes) return `${remain}s`;
  return `${minutes}m ${remain}s`;
}

function formatScore(value, verdict) {
  if (value == null) return "-";
  const label = typeof verdict === "string" && verdict ? ` (${verdict})` : "";
  return `${Number(value).toFixed(2)}${label}`;
}

function setFormStatus(message, tone = "") {
  elements.formStatus.textContent = message;
  elements.formStatus.className = tone ? `hint ${tone}` : "hint";
}

function formatStyleSummary(styleProfile) {
  if (!styleProfile) return "-";
  const lines = [];
  if (styleProfile.summary) lines.push(styleProfile.summary);
  if (styleProfile.narrative_person) lines.push(`叙述视角：${styleProfile.narrative_person}`);
  if (styleProfile.pacing) lines.push(`节奏：${styleProfile.pacing}`);
  if (styleProfile.tone_keywords?.length) lines.push(`语气关键词：${styleProfile.tone_keywords.join(" / ")}`);
  if (styleProfile.dialogue_style) lines.push(`对白风格：${styleProfile.dialogue_style}`);
  if (styleProfile.signature_devices?.length) lines.push(`标志写法：${styleProfile.signature_devices.join("；")}`);
  return lines.join("\n\n");
}

function formatStorySummary(storyState) {
  if (!storyState) return "-";
  const lines = [];
  if (storyState.summary) lines.push(storyState.summary);
  if (storyState.active_conflicts?.length) {
    lines.push(`当前冲突：\n- ${storyState.active_conflicts.join("\n- ")}`);
  }
  if (storyState.main_characters?.length) {
    const topCharacters = storyState.main_characters
      .slice(0, 4)
      .map((item) => `${item.name}${item.role ? `：${item.role}` : ""}`);
    lines.push(`主要角色：${topCharacters.join("；")}`);
  }
  if (storyState.major_relationships?.length) {
    lines.push(`关键关系：${storyState.major_relationships.slice(0, 4).join("；")}`);
  }
  return lines.join("\n\n");
}

function formatQualitySummary(report) {
  if (!report) return "-";
  const lines = [`分数：${Number(report.score || 0).toFixed(3)}`, `结论：${report.verdict || "-"}`];
  if (report.used_deepeval != null) lines.push(`DeepEval：${report.used_deepeval ? "是" : "否"}`);
  if (report.issues?.length) lines.push(`问题：\n- ${report.issues.join("\n- ")}`);
  return lines.join("\n");
}

function formatConsistencySummary(report) {
  if (!report) return "-";
  const lines = [`通过：${report.passed ? "是" : "否"}`];
  if (report.issues?.length) lines.push(`问题：\n- ${report.issues.join("\n- ")}`);
  return lines.join("\n");
}

function renderRunList(runs) {
  state.runCache = runs;
  if (!runs.length) {
    elements.runList.innerHTML = '<p class="hint">暂无任务记录。</p>';
    return;
  }

  elements.runList.innerHTML = runs
    .map((run) => {
      const activeClass = run.id === state.activeRunId ? " active" : "";
      return `
        <article class="run-item${activeClass}" data-run-id="${escapeHtml(run.id)}">
          <span class="label">${escapeHtml(run.status)}</span>
          <strong>${escapeHtml(run.session_name)}</strong>
          <p>${escapeHtml(run.input_filename)}</p>
          <p>${escapeHtml(run.progress?.message || "等待开始")}</p>
        </article>
      `;
    })
    .join("");

  for (const item of elements.runList.querySelectorAll(".run-item")) {
    item.addEventListener("click", () => loadRun(item.dataset.runId));
  }
}

function renderLogs(lines) {
  elements.runLogs.innerHTML = "";
  if (!lines?.length) {
    elements.runLogs.innerHTML = '<div class="log-line">暂无日志</div>';
    return;
  }
  for (const line of lines) {
    const node = document.createElement("div");
    node.className = "log-line";
    node.textContent = line;
    elements.runLogs.appendChild(node);
  }
}

function renderArtifacts(paths) {
  elements.artifactList.innerHTML = "";
  const mapping = [
    ["run_manifest.json", paths?.manifest],
    ["stage1_snapshot.json", paths?.stage1_snapshot],
    ["latest skeleton", paths?.latest_skeleton],
    ["latest draft", paths?.latest_draft],
    ["latest output", paths?.latest_output],
    ["story_graph.mmd", paths?.story_graph],
  ].filter((item) => item[1]);

  if (!mapping.length) {
    elements.artifactList.innerHTML = '<div class="path-line"><strong>暂无产物路径</strong></div>';
    return;
  }

  elements.artifactList.innerHTML = mapping
    .map(
      ([label, value]) => `
        <div class="path-line">
          <strong>${escapeHtml(label)}</strong>
          <code>${escapeHtml(value)}</code>
        </div>
      `
    )
    .join("");
}

function renderThreads(threads) {
  elements.threadsList.innerHTML = "";
  if (!threads?.length) {
    elements.threadsList.innerHTML = '<div class="thread-item"><strong>当前没有未收束伏笔</strong></div>';
    return;
  }
  elements.threadsList.innerHTML = threads
    .slice(0, 8)
    .map(
      (thread) => `
        <div class="thread-item">
          <strong>${escapeHtml(thread.id)} · ${escapeHtml(thread.status)}</strong>
          <span>${escapeHtml(thread.description)}</span>
          <span>首次出现：${escapeHtml(thread.introduced_at)}，最近推进：${escapeHtml(thread.last_advanced)}</span>
        </div>
      `
    )
    .join("");
}

function renderChapterList(chapters) {
  elements.chapterList.innerHTML = "";
  if (!chapters?.length) {
    elements.chapterList.innerHTML = '<div class="chapter-item"><strong>还没有章节结果</strong></div>';
    return;
  }

  elements.chapterList.innerHTML = chapters
    .map(
      (chapter) => `
        <div class="chapter-item">
          <strong>第 ${escapeHtml(chapter.chapter_number)} 章 · ${escapeHtml(chapter.status)}</strong>
          <div class="chapter-meta">
            <span>耗时 ${escapeHtml(formatDuration(chapter.elapsed_seconds))}</span>
            <span>质检 ${escapeHtml(formatScore(chapter.quality_score, chapter.quality_verdict))}</span>
            <span>一致性 ${chapter.consistency_passed == null ? "-" : chapter.consistency_passed ? "通过" : "未过"}</span>
          </div>
          <span>${escapeHtml(chapter.chapter_goal || "未记录章节目标")}</span>
        </div>
      `
    )
    .join("");
}

function renderRun(run) {
  elements.emptyState.classList.add("hidden");
  elements.runView.classList.remove("hidden");

  elements.runId.textContent = run.id;
  elements.runSession.textContent = run.session_name;
  elements.runStatus.textContent = run.status;
  elements.runStatus.className = `status-${run.status}`;

  const percent = Number(run.progress?.percent || 0);
  elements.progressFill.style.width = `${percent}%`;
  elements.progressMessage.textContent = run.progress?.message || "等待开始";
  elements.progressPercent.textContent = `${percent}%`;
  elements.progressCount.textContent = run.progress?.completed_label || "0/0";

  elements.metricCalls.textContent = formatNumber(run.metrics?.total_calls || 0);
  elements.metricTokens.textContent = formatNumber(run.metrics?.total_tokens || 0);
  elements.metricCost.textContent = formatCurrency(run.metrics?.total_cost_usd || 0);
  elements.metricChapters.textContent = `${run.metrics?.completed_chapters || 0} / ${run.metrics?.chapter_count || 0}`;
  elements.metricQuality.textContent = formatScore(
    run.metrics?.latest_quality_score,
    run.metrics?.latest_quality_verdict
  );
  elements.metricConsistency.textContent =
    run.metrics?.consistency_passed == null ? "-" : run.metrics.consistency_passed ? "通过" : "未过";

  elements.styleSummary.textContent = formatStyleSummary(run.style_profile);
  elements.storySummary.textContent = formatStorySummary(run.story_state);
  elements.goalSummary.textContent = run.latest_chapter_goal || "-";
  elements.qualitySummary.textContent = formatQualitySummary(run.latest_quality_report);
  elements.consistencySummary.textContent = formatConsistencySummary(run.latest_consistency_report);
  const latestOutputPath =
    run.artifact_paths?.latest_output ||
    (Array.isArray(run.output_paths) && run.output_paths.length ? run.output_paths[run.output_paths.length - 1] : "-");
  elements.outputPath.textContent = latestOutputPath;
  elements.outputPreview.textContent = run.latest_output_preview || "-";

  renderArtifacts(run.artifact_paths);
  renderThreads(run.unresolved_threads);
  renderChapterList(run.chapter_summaries);
  renderLogs(run.log_messages || []);

  if (run.status === "failed" && run.error_message) {
    elements.errorBanner.textContent = run.error_message;
    elements.errorBanner.classList.remove("hidden");
  } else {
    elements.errorBanner.textContent = "";
    elements.errorBanner.classList.add("hidden");
  }
}

async function fetchJson(url, options) {
  const response = await fetch(url, options);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || payload.message || `请求失败：${response.status}`);
  }
  return payload;
}

async function refreshRuns({ autoSelect = false } = {}) {
  const runs = await fetchJson("/api/runs");
  renderRunList(runs);
  if (autoSelect && runs.length && !state.activeRunId) {
    await loadRun(runs[0].id);
  }
}

async function loadRun(runId) {
  const run = await fetchJson(`/api/runs/${runId}`);
  state.activeRunId = runId;
  renderRun(run);
  renderRunList(state.runCache);
  if (run.status === "queued" || run.status === "running") {
    startPolling(runId);
  } else {
    stopPolling();
  }
}

function stopPolling() {
  if (state.pollTimer) {
    window.clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function startPolling(runId) {
  stopPolling();
  state.pollTimer = window.setInterval(async () => {
    try {
      const run = await fetchJson(`/api/runs/${runId}`);
      renderRun(run);
      await refreshRuns();
      if (run.status !== "queued" && run.status !== "running") {
        stopPolling();
      }
    } catch (error) {
      stopPolling();
      setFormStatus(`轮询失败：${error.message}`, "tone-error");
    }
  }, 2200);
}

elements.fileInput.addEventListener("change", () => {
  const file = elements.fileInput.files?.[0];
  elements.selectedFileName.textContent = file ? file.name : "选择一个 `.txt` 文件";
});

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(elements.form);
  elements.submitButton.disabled = true;
  setFormStatus("正在创建任务...");

  try {
    const payload = await fetchJson("/api/runs", {
      method: "POST",
      body: formData,
    });
    setFormStatus("任务已创建，开始轮询。");
    await refreshRuns();
    await loadRun(payload.id);
  } catch (error) {
    setFormStatus(`提交失败：${error.message}`, "tone-error");
  } finally {
    elements.submitButton.disabled = false;
  }
});

window.addEventListener("load", async () => {
  try {
    await refreshRuns({ autoSelect: true });
  } catch (error) {
    setFormStatus(`初始化失败：${error.message}`, "tone-error");
  }
});
