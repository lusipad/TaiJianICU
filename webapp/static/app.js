const state = {
  activeRunId: null,
  activeBenchmarkKey: null,
  pollTimer: null,
  benchmarkCache: [],
  runCache: [],
};

const elements = {
  form: document.getElementById("run-form"),
  submitButton: document.getElementById("submit-button"),
  formStatus: document.getElementById("form-status"),
  fileInput: document.getElementById("file-input"),
  selectedFileName: document.getElementById("selected-file-name"),
  runList: document.getElementById("run-list"),
  benchmarkList: document.getElementById("benchmark-list"),
  benchmarkSummary: document.getElementById("benchmark-summary"),
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
  worldSummary: document.getElementById("world-summary"),
  lorebookSummary: document.getElementById("lorebook-summary"),
  goalSummary: document.getElementById("goal-summary"),
  briefSummary: document.getElementById("brief-summary"),
  evaluationSummary: document.getElementById("evaluation-summary"),
  skeletonCandidateList: document.getElementById("skeleton-candidate-list"),
  draftCandidateList: document.getElementById("draft-candidate-list"),
  artifactList: document.getElementById("artifact-list"),
  referenceList: document.getElementById("reference-list"),
  arcList: document.getElementById("arc-list"),
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

function formatWorldSummary(worldModel) {
  if (!worldModel) return "-";
  const lines = [];
  if (worldModel.summary) lines.push(worldModel.summary);
  if (worldModel.world_tensions?.length) lines.push(`世界张力：${worldModel.world_tensions.join("；")}`);
  if (worldModel.open_mysteries?.length) lines.push(`未解谜团：${worldModel.open_mysteries.join("；")}`);
  if (worldModel.canon_facts?.length) {
    lines.push(
      `硬设定：\n- ${worldModel.canon_facts
        .slice(0, 4)
        .map((item) => item.statement)
        .join("\n- ")}`
    );
  }
  return lines.join("\n\n");
}

function formatLorebookSummary(lorebook) {
  if (!lorebook?.entries?.length) return "-";
  return lorebook.entries
    .slice(0, 6)
    .map((entry) => `${entry.hard_constraint ? "[硬约束]" : "[参考]"} ${entry.title}：${entry.content}`)
    .join("\n\n");
}

function formatBriefSummary(brief) {
  if (!brief) return "-";
  const lines = [];
  if (brief.chapter_goal) lines.push(`目标：${brief.chapter_goal}`);
  if (brief.chapter_note) lines.push(`备注：${brief.chapter_note}`);
  if (brief.must_happen?.length) lines.push(`必须发生：\n- ${brief.must_happen.join("\n- ")}`);
  if (brief.constraints?.length) {
    lines.push(`约束：\n- ${brief.constraints.map((item) => item.content).join("\n- ")}`);
  }
  return lines.join("\n\n");
}

function formatEvaluationSummary(evaluation) {
  if (!evaluation) return "-";
  const score = evaluation.score || {};
  const lines = [
    `摘要：${evaluation.summary || "-"}`,
    `Continuity：${Number(score.continuity_score || 0).toFixed(2)}`,
    `Character：${Number(score.character_score || 0).toFixed(2)}`,
    `World：${Number(score.world_consistency_score || 0).toFixed(2)}`,
    `Novelty：${Number(score.novelty_score || 0).toFixed(2)}`,
    `Arc Progress：${Number(score.arc_progress_score || 0).toFixed(2)}`,
    `需重试：${evaluation.should_retry ? "是" : "否"}`,
  ];
  if (evaluation.flags?.length) {
    lines.push(`Flags：\n- ${evaluation.flags.map((item) => `${item.code} ${item.message}`).join("\n- ")}`);
  }
  return lines.join("\n");
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

function renderBenchmarkList(items) {
  state.benchmarkCache = items || [];
  if (!items?.length) {
    elements.benchmarkList.innerHTML = '<p class="hint">暂无 benchmark 报告。</p>';
    elements.benchmarkSummary.textContent = "-";
    state.activeBenchmarkKey = null;
    return;
  }
  elements.benchmarkList.innerHTML = items
    .map(
      (item) => `
        <article
          class="run-item benchmark-item${state.activeBenchmarkKey === `${item.dataset_name}/${item.case_name}` ? " active" : ""}"
          data-dataset="${escapeHtml(item.dataset_name)}"
          data-case="${escapeHtml(item.case_name)}"
        >
          <span class="label">${escapeHtml(item.winner)}</span>
          <strong>${escapeHtml(item.dataset_name)} / ${escapeHtml(item.case_name)}</strong>
          <p>prefix ${escapeHtml(item.prefix_chapter_count)} -> target ${escapeHtml(item.target_chapter_number)}</p>
          <p>confidence ${escapeHtml(Number(item.confidence).toFixed(2))}</p>
        </article>
      `
    )
    .join("");
  for (const item of elements.benchmarkList.querySelectorAll(".benchmark-item")) {
    item.addEventListener("click", () => loadBenchmark(item.dataset.dataset, item.dataset.case));
  }
}

function renderBenchmarkDetail(detail) {
  elements.benchmarkSummary.textContent = [
    `数据集：${detail.dataset_name}`,
    `Case：${detail.case_name}`,
    `Winner：${detail.winner}`,
    `Confidence：${Number(detail.confidence).toFixed(2)}`,
    `System Score：${Number(detail.system_score).toFixed(2)}`,
    `Baseline Score：${Number(detail.baseline_score).toFixed(2)}`,
    `System Summary：${detail.system_summary || "-"}`,
    `Baseline Summary：${detail.baseline_summary || "-"}`,
    `System Strengths：${detail.system_strengths?.length ? detail.system_strengths.join("；") : "-"}`,
    `Baseline Strengths：${detail.baseline_strengths?.length ? detail.baseline_strengths.join("；") : "-"}`,
    `System Weaknesses：${detail.system_weaknesses?.length ? detail.system_weaknesses.join("；") : "-"}`,
    `Baseline Weaknesses：${detail.baseline_weaknesses?.length ? detail.baseline_weaknesses.join("；") : "-"}`,
    `System Elapsed：${formatDuration(detail.system_elapsed_seconds)}`,
    `Baseline Elapsed：${formatDuration(detail.baseline_elapsed_seconds)}`,
    `Total Cost：${formatCurrency(detail.total_cost_usd)}`,
    `Total Tokens：${formatNumber(detail.total_tokens)}`,
    `System Output：${detail.system_output_path}`,
    `Baseline Output：${detail.baseline_output_path}`,
    `Reference：${detail.reference_path}`,
    `Report JSON：${detail.report_json_path}`,
    `Report Markdown：${detail.report_markdown_path}`,
    `Reasoning：`,
    ...(detail.pairwise_reasoning?.length ? detail.pairwise_reasoning : ["-"]),
  ].join("\n");
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
    ["world_model.json", paths?.world_model],
    ["lorebook.json", paths?.lorebook],
    ["selected_references.json", paths?.selected_references],
    ["latest skeleton", paths?.latest_skeleton],
    ["latest chapter brief", paths?.latest_chapter_brief],
    ["latest chapter evaluation", paths?.latest_chapter_evaluation],
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

function renderCandidatePaths(element, paths, emptyLabel) {
  element.innerHTML = "";
  if (!paths?.length) {
    element.innerHTML = `<div class="path-line"><strong>${escapeHtml(emptyLabel)}</strong></div>`;
    return;
  }
  element.innerHTML = paths
    .map(
      (value, index) => `
        <div class="path-line">
          <strong>Candidate ${index + 1}</strong>
          <code>${escapeHtml(value)}</code>
        </div>
      `
    )
    .join("");
}

function renderReferences(references) {
  elements.referenceList.innerHTML = "";
  if (!references?.length) {
    elements.referenceList.innerHTML = '<div class="thread-item"><strong>当前没有选中的参考策略</strong></div>';
    return;
  }
  elements.referenceList.innerHTML = references
    .map(
      (item) => `
        <div class="thread-item">
          <strong>${escapeHtml(item.name)} · ${escapeHtml(item.reference_type)}</strong>
          <span>${escapeHtml((item.abstract_traits || []).map((trait) => trait.label).join("；") || "无抽象特征")}</span>
          <span>${escapeHtml((item.allowed_influences || []).join("；") || "无影响域")}</span>
        </div>
      `
    )
    .join("");
}

function renderArcList(arcs) {
  elements.arcList.innerHTML = "";
  if (!arcs?.length) {
    elements.arcList.innerHTML = '<div class="chapter-item"><strong>当前没有 arc 规划</strong></div>';
    return;
  }
  elements.arcList.innerHTML = arcs
    .map(
      (arc) => `
        <div class="chapter-item">
          <strong>${escapeHtml(arc.arc_id)} · ${escapeHtml((arc.chapters_span || []).join("-"))}</strong>
          <div class="chapter-meta">
            <span>${escapeHtml(arc.phase || "-")}</span>
            <span>${escapeHtml(arc.arc_theme || "-")}</span>
          </div>
          <span>${escapeHtml(arc.arc_goal || arc.summary || "-")}</span>
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
  elements.worldSummary.textContent = formatWorldSummary(run.world_model);
  elements.lorebookSummary.textContent = formatLorebookSummary(run.lorebook);
  elements.goalSummary.textContent = run.latest_chapter_goal || "-";
  elements.briefSummary.textContent = formatBriefSummary(run.latest_chapter_brief);
  elements.evaluationSummary.textContent = formatEvaluationSummary(run.latest_chapter_evaluation);
  elements.qualitySummary.textContent = formatQualitySummary(run.latest_quality_report);
  elements.consistencySummary.textContent = formatConsistencySummary(run.latest_consistency_report);
  const latestOutputPath =
    run.artifact_paths?.latest_output ||
    (Array.isArray(run.output_paths) && run.output_paths.length ? run.output_paths[run.output_paths.length - 1] : "-");
  elements.outputPath.textContent = latestOutputPath;
  elements.outputPreview.textContent = run.latest_output_preview || "-";

  renderArtifacts(run.artifact_paths);
  renderCandidatePaths(elements.skeletonCandidateList, run.latest_skeleton_candidate_paths, "暂无骨架候选");
  renderCandidatePaths(elements.draftCandidateList, run.latest_draft_candidate_paths, "暂无正文候选");
  renderReferences(run.selected_references);
  renderArcList(run.arc_outlines);
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

async function refreshBenchmarks() {
  const items = await fetchJson("/api/benchmarks");
  renderBenchmarkList(items);
  if (!items.length) {
    return;
  }
  const fallback = items[0];
  const [datasetName, caseName] = state.activeBenchmarkKey?.split("/") || [];
  const current =
    items.find((item) => item.dataset_name === datasetName && item.case_name === caseName) || fallback;
  await loadBenchmark(current.dataset_name, current.case_name, { rerenderList: false });
}

async function loadBenchmark(datasetName, caseName, { rerenderList = true } = {}) {
  const detail = await fetchJson(
    `/api/benchmarks/${encodeURIComponent(datasetName)}/${encodeURIComponent(caseName)}`
  );
  state.activeBenchmarkKey = `${detail.dataset_name}/${detail.case_name}`;
  renderBenchmarkDetail(detail);
  if (rerenderList) {
    renderBenchmarkList(state.benchmarkCache);
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
  for (const key of [
    "new_character_budget",
    "new_location_budget",
    "new_faction_budget",
    "skeleton_candidates",
    "draft_candidates",
  ]) {
    if (!String(formData.get(key) || "").trim()) {
      formData.delete(key);
    }
  }
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
    await refreshBenchmarks();
  } catch (error) {
    setFormStatus(`初始化失败：${error.message}`, "tone-error");
  }
});
