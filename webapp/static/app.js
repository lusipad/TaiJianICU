// ── Onboarding Modal ──
function initOnboarding() {
  const modal = document.getElementById("onboarding-modal");
  if (!modal) return;
  if (localStorage.getItem("tkOnboardingDone")) return;

  const steps = modal.querySelectorAll(".onboarding-step");
  const nextBtn = document.getElementById("onboarding-next");
  const skipBtn = document.getElementById("onboarding-skip");
  const noShowCheck = document.getElementById("onboarding-no-show");
  let currentStep = 0;

  function showStep(index) {
    steps.forEach((step, i) => {
      step.classList.toggle("hidden", i !== index);
    });
    nextBtn.textContent = index < steps.length - 1 ? "下一步" : "开始使用";
  }

  function closeModal() {
    if (noShowCheck.checked) {
      localStorage.setItem("tkOnboardingDone", "1");
    }
    modal.classList.add("hidden");
  }

  nextBtn.addEventListener("click", () => {
    if (currentStep < steps.length - 1) {
      currentStep++;
      showStep(currentStep);
    } else {
      closeModal();
    }
  });

  skipBtn.addEventListener("click", closeModal);

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });

  showStep(0);
  setTimeout(() => modal.classList.remove("hidden"), 500);
}

document.addEventListener("DOMContentLoaded", initOnboarding);

const state = {
  activeRunId: null,
  activeRunDetail: null,
  activeBenchmarkKey: null,
  activeSourceTab: "excerpt",
  activeOutputTab: "combined",
  activeWorkspaceTab: "overview",
  activeSidebarTab: "runs",
  exampleCache: [],
  exampleDetailCache: {},
  pollTimer: null,
  benchmarkCache: [],
  runtimeConfig: null,
  runCache: [],
  sourceTextCache: {},
};

const elements = {
  form: document.getElementById("run-form"),
  submitButton: document.getElementById("submit-button"),
  formStatus: document.getElementById("form-status"),
  fileInput: document.getElementById("file-input"),
  selectedFileName: document.getElementById("selected-file-name"),
  tryExampleButton: document.getElementById("try-example-button"),
  loadExampleButton: document.getElementById("load-example-button"),
  emptyExampleButton: document.getElementById("empty-example-button"),
  emptyFillExampleButton: document.getElementById("empty-fill-example-button"),
  exampleDescription: document.getElementById("example-description"),
  resetModelsButton: document.getElementById("reset-models-button"),
  clearApiConfigButton: document.getElementById("clear-api-config-button"),
  openAdvancedOptionsButton: document.getElementById("open-advanced-options-button"),
  runtimeModelHint: document.getElementById("runtime-model-hint"),
  runtimeApiHint: document.getElementById("runtime-api-hint"),
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
  modelSummary: document.getElementById("model-summary"),
  styleSummary: document.getElementById("style-summary"),
  storySummary: document.getElementById("story-summary"),
  workSkillSummary: document.getElementById("work-skill-summary"),
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
  revivalDiagnosisSummary: document.getElementById("revival-diagnosis-summary"),
  blindChallenge: document.getElementById("blind-challenge"),
  threadsList: document.getElementById("threads-list"),
  chapterList: document.getElementById("chapter-list"),
  sourcePreviewLabel: document.getElementById("source-preview-label"),
  sourcePreviewMeta: document.getElementById("source-preview-meta"),
  sourcePreview: document.getElementById("source-preview"),
  outputPreviewLabel: document.getElementById("output-preview-label"),
  outputPreviewMeta: document.getElementById("output-preview-meta"),
  outputPath: document.getElementById("output-path"),
  outputPreview: document.getElementById("output-preview"),
  runLogs: document.getElementById("run-logs"),
  styleModelInput: document.getElementById("style-model-input"),
  plotModelInput: document.getElementById("plot-model-input"),
  draftModelInput: document.getElementById("draft-model-input"),
  qualityModelInput: document.getElementById("quality-model-input"),
  lightragModelInput: document.getElementById("lightrag-model-input"),
  apiBaseUrlInput: document.getElementById("api-base-url-input"),
  apiKeyInput: document.getElementById("api-key-input"),
  goalHintInput: document.querySelector('textarea[name="goal_hint"]'),
  modelOptions: document.getElementById("model-options"),
  advancedOptionsDetails: document.getElementById("advanced-options"),
  workspaceTabs: Array.from(document.querySelectorAll(".workspace-tab")),
  workspacePanels: Array.from(document.querySelectorAll("[data-tab-panel]")),
  sidebarTabs: Array.from(document.querySelectorAll(".inspector-tab")),
  sidebarPanels: Array.from(document.querySelectorAll("[data-sidebar-panel]")),
  sourceTabButtons: Array.from(document.querySelectorAll("[data-source-tab-target]")),
  outputTabButtons: Array.from(document.querySelectorAll("[data-output-tab-target]")),
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function renderInlineMarkdown(value) {
  return escapeHtml(value ?? "")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/\*([^*]+)\*/g, "<em>$1</em>");
}

function renderMarkdownPreview(markdown) {
  const normalized = String(markdown || "")
    .replace(/\r\n/g, "\n")
    .trim();
  if (!normalized || normalized === "-") {
    return '<p class="markdown-empty">暂无正文预览</p>';
  }

  const blocks = normalized.split(/\n\s*\n/).map((block) => block.trim()).filter(Boolean);
  return blocks
    .map((block) => {
      const lines = block.split("\n").map((line) => line.trimEnd());
      const headingMatch = lines.length === 1 ? lines[0].match(/^(#{1,6})\s+(.+)$/) : null;
      if (headingMatch) {
        const level = Math.min(6, headingMatch[1].length);
        return `<h${level}>${renderInlineMarkdown(headingMatch[2])}</h${level}>`;
      }

      const thematicBreak = lines.length === 1 && /^([-*_])(?:\s*\1){2,}$/.test(lines[0].trim());
      if (thematicBreak) {
        return "<hr>";
      }

      const unorderedList = lines.every((line) => /^[-*]\s+/.test(line.trim()));
      if (unorderedList) {
        const items = lines
          .map((line) => `<li>${renderInlineMarkdown(line.replace(/^[-*]\s+/, ""))}</li>`)
          .join("");
        return `<ul>${items}</ul>`;
      }

      const orderedList = lines.every((line) => /^\d+\.\s+/.test(line.trim()));
      if (orderedList) {
        const items = lines
          .map((line) => `<li>${renderInlineMarkdown(line.replace(/^\d+\.\s+/, ""))}</li>`)
          .join("");
        return `<ol>${items}</ol>`;
      }

      const quoteBlock = lines.every((line) => line.trim().startsWith(">"));
      if (quoteBlock) {
        const content = lines
          .map((line) => renderInlineMarkdown(line.replace(/^>\s?/, "")))
          .join("<br>");
        return `<blockquote><p>${content}</p></blockquote>`;
      }

      const paragraph = lines
        .map((line) => renderInlineMarkdown(line.trim()))
        .filter(Boolean)
        .join("<br>");
      return `<p>${paragraph}</p>`;
    })
    .join("");
}

function splitOutputMarkdown(markdown) {
  const normalized = String(markdown || "")
    .replace(/\r\n/g, "\n")
    .trim();
  if (!normalized || normalized === "-") {
    return { body: "", noteBody: "" };
  }

  const notePatterns = [
    /\n---\s*\n\*\*(改写说明|创作说明|优化说明|续写说明)\*\*[:：]?\s*([\s\S]*)$/u,
    /\n#{1,6}\s*(改写说明|创作说明|优化说明|续写说明)\s*\n([\s\S]*)$/u,
  ];
  for (const pattern of notePatterns) {
    const match = pattern.exec(normalized);
    if (!match || typeof match.index !== "number") continue;
    const body = normalized.slice(0, match.index).trim();
    const noteBody = String(match[2] || "").trim();
    if (body && noteBody) {
      return { body, noteBody };
    }
  }

  return { body: normalized, noteBody: "" };
}

function formatNumber(value) {
  return new Intl.NumberFormat("zh-CN").format(Number(value || 0));
}

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(6)}`;
}

function formatRunStatus(value) {
  switch (value) {
    case "queued":
      return "排队中";
    case "running":
      return "运行中";
    case "analyzing":
      return "分析中";
    case "awaiting_arc_selection":
      return "等待选择人物走向";
    case "generating":
      return "生成中";
    case "completed":
      return "已完成";
    case "completed_with_warnings":
      return "已完成，有警告";
    case "failed":
      return "失败";
    default:
      return value || "-";
  }
}

function isLiveRunStatus(status) {
  return ["queued", "running", "analyzing", "generating"].includes(status);
}

function formatBenchmarkWinner(value) {
  switch (value) {
    case "system":
      return "系统版胜出";
    case "baseline":
      return "基线版胜出";
    case "tie":
      return "平局";
    default:
      return value || "-";
  }
}

function formatDuration(seconds) {
  if (seconds == null || Number.isNaN(Number(seconds))) return "-";
  const totalSeconds = Math.max(0, Math.round(Number(seconds)));
  const minutes = Math.floor(totalSeconds / 60);
  const remain = totalSeconds % 60;
  if (!minutes) return `${remain} 秒`;
  return `${minutes} 分 ${remain} 秒`;
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

function formatWorkSkillSummary(workSkill) {
  if (!workSkill) return "-";
  const lines = [];
  if (workSkill.work_title) lines.push(`作品：${workSkill.work_title}`);
  if (workSkill.voice_rules?.length) lines.push(`声口：\n- ${workSkill.voice_rules.slice(0, 5).join("\n- ")}`);
  if (workSkill.rhythm_rules?.length) lines.push(`节奏：\n- ${workSkill.rhythm_rules.slice(0, 5).join("\n- ")}`);
  if (workSkill.open_threads?.length) lines.push(`未收束：\n- ${workSkill.open_threads.slice(0, 5).join("\n- ")}`);
  if (workSkill.forbidden_moves?.length) lines.push(`禁区：\n- ${workSkill.forbidden_moves.slice(0, 5).join("\n- ")}`);
  return lines.join("\n\n") || "-";
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
    `连贯性：${Number(score.continuity_score || 0).toFixed(2)}`,
    `人物一致性：${Number(score.character_score || 0).toFixed(2)}`,
    `世界一致性：${Number(score.world_consistency_score || 0).toFixed(2)}`,
    `新意：${Number(score.novelty_score || 0).toFixed(2)}`,
    `情节推进：${Number(score.arc_progress_score || 0).toFixed(2)}`,
    `需重试：${evaluation.should_retry ? "是" : "否"}`,
  ];
  if (evaluation.flags?.length) {
    lines.push(`风险标记：\n- ${evaluation.flags.map((item) => `${item.code} ${item.message}`).join("\n- ")}`);
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

function formatRevivalDiagnosis(diagnosis) {
  if (!diagnosis) return "-";
  const lines = [`状态：${diagnosis.status || "-"}`, `重试：${diagnosis.retry_count || 0}`];
  if (diagnosis.voice_fit != null) lines.push(`声口贴合：${Number(diagnosis.voice_fit).toFixed(2)}`);
  if (diagnosis.plot_alignment != null) lines.push(`剧情贴合：${Number(diagnosis.plot_alignment).toFixed(2)}`);
  if (diagnosis.character_fit != null) lines.push(`人物贴合：${Number(diagnosis.character_fit).toFixed(2)}`);
  if (diagnosis.contamination_hits?.length) {
    lines.push(`污染命中：\n- ${diagnosis.contamination_hits.map((hit) => hit.label).join("\n- ")}`);
  }
  if (diagnosis.failure_reasons?.length) {
    lines.push(`失败原因：\n- ${diagnosis.failure_reasons.join("\n- ")}`);
  }
  if (diagnosis.recommended_fix) lines.push(`建议：${diagnosis.recommended_fix}`);
  return lines.join("\n");
}

function formatModelSummary(request) {
  if (!request) return "-";
  const config = state.runtimeConfig || {};
  const lines = [
    `风格分析模型：${request.style_model || config.style_model || "-"}`,
    `情节规划模型：${request.plot_model || config.plot_model || "-"}`,
    `正文生成模型：${request.draft_model || config.draft_model || "-"}`,
    `质检评估模型：${request.quality_model || config.quality_model || "-"}`,
    `原著索引模型：${request.lightrag_model_name || config.lightrag_model_name || "-"}`,
  ];
  return lines.join("\n");
}

function applyRuntimeConfig(config) {
  state.runtimeConfig = config;
  const fields = [
    [elements.styleModelInput, config.style_model],
    [elements.plotModelInput, config.plot_model],
    [elements.draftModelInput, config.draft_model],
    [elements.qualityModelInput, config.quality_model],
    [elements.lightragModelInput, config.lightrag_model_name],
  ];
  for (const [element, value] of fields) {
    if (!element) continue;
    element.value = value || "";
    element.placeholder = value || "";
  }
  elements.modelOptions.innerHTML = (config.model_options || [])
    .map((item) => `<option value="${escapeHtml(item)}"></option>`)
    .join("");
  if (elements.runtimeModelHint) {
    elements.runtimeModelHint.textContent = `默认：规划 ${config.plot_model} / 正文 ${config.draft_model} / 质检 ${config.quality_model}`;
  }
  if (elements.apiBaseUrlInput) {
    elements.apiBaseUrlInput.placeholder = config.api_base_url || "留空则使用部署默认 endpoint";
  }
  if (elements.runtimeApiHint) {
    elements.runtimeApiHint.textContent = config.api_base_url
      ? `如果你想用自己的 endpoint / Key，这里可以直接填。当前部署默认 endpoint：${config.api_base_url}；如果留空，会继续走服务端默认配置。仅当前页面有效，刷新后清空，不会写入任务记录。`
      : "如果你想用自己的 endpoint / Key，这里可以直接填。留空时会继续走服务端默认配置。仅当前页面有效，刷新后清空，不会写入任务记录。";
  }
}

function resetModelInputs() {
  if (!state.runtimeConfig) return;
  applyRuntimeConfig(state.runtimeConfig);
}

function clearApiConfigInputs() {
  if (elements.apiBaseUrlInput) elements.apiBaseUrlInput.value = "";
  if (elements.apiKeyInput) elements.apiKeyInput.value = "";
}

function focusApiConfig({ scroll = true } = {}) {
  const container = document.getElementById("bring-your-own-api");
  if (scroll) {
    container?.scrollIntoView({ behavior: "smooth", block: "start" });
  }
  const targetInput = elements.apiBaseUrlInput || elements.apiKeyInput;
  if (targetInput) {
    window.setTimeout(
      () => targetInput.focus({ preventScroll: true }),
      scroll ? 220 : 0
    );
  }
}

function openAdvancedOptions({ scroll = true } = {}) {
  if (!elements.advancedOptionsDetails) return;
  elements.advancedOptionsDetails.open = true;
  if (scroll) {
    elements.advancedOptionsDetails.scrollIntoView({ behavior: "smooth", block: "start" });
  }
}

function applyStudioHashIntent() {
  const hash = window.location.hash;
  if (hash === "#bring-your-own-api") {
    focusApiConfig({ scroll: false });
    return;
  }
  if (hash === "#advanced-options") {
    openAdvancedOptions({ scroll: false });
  }
}

function collectRunFormData() {
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
  for (const key of ["api_base_url", "api_key", "session_name", "goal_hint"]) {
    if (!String(formData.get(key) || "").trim()) {
      formData.delete(key);
    }
  }
  return formData;
}

function setActionBusy(isBusy) {
  elements.submitButton.disabled = isBusy;
  if (elements.tryExampleButton) elements.tryExampleButton.disabled = isBusy;
  if (elements.loadExampleButton) elements.loadExampleButton.disabled = isBusy;
  if (elements.emptyExampleButton) elements.emptyExampleButton.disabled = isBusy;
  if (elements.emptyFillExampleButton) elements.emptyFillExampleButton.disabled = isBusy;
}

function renderExamples(items) {
  state.exampleCache = items || [];
  const example = state.exampleCache[0];
  if (!elements.exampleDescription) return;
  if (!example) {
    elements.exampleDescription.textContent = "当前没有可用示例。请先上传自己的 .txt，或检查服务端内置样例是否启用。";
    if (elements.tryExampleButton) elements.tryExampleButton.disabled = true;
    if (elements.loadExampleButton) elements.loadExampleButton.disabled = true;
    if (elements.emptyExampleButton) elements.emptyExampleButton.disabled = true;
    if (elements.emptyFillExampleButton) elements.emptyFillExampleButton.disabled = true;
    return;
  }
  if (elements.tryExampleButton) {
    elements.tryExampleButton.textContent = `快速试看：${example.title}`;
  }
  if (elements.loadExampleButton) {
    elements.loadExampleButton.textContent = `按当前配置试跑：${example.title}`;
  }
  if (elements.emptyExampleButton) {
    elements.emptyExampleButton.textContent = `快速试看：${example.title}`;
  }
  if (elements.emptyFillExampleButton) {
    elements.emptyFillExampleButton.textContent = `按当前配置试跑：${example.title}`;
  }
  elements.exampleDescription.textContent = [
    `${example.title} · ${example.description}`,
    "快速试看只加载固定结果，不消耗你当前填写的 endpoint / Key。",
    "按当前配置试跑样例会真的调用当前页面配置；如果你没有填写自己的 Key，则仍受平台单 IP 小额度限制。需要长期使用时，也可以切到自己的 Key 或本地版本。",
  ]
    .filter(Boolean)
    .join(" ");
}

async function loadExamples() {
  try {
    const items = await fetchJson("/api/examples");
    renderExamples(items);
  } catch (error) {
    renderExamples([]);
    if (elements.exampleDescription) {
      elements.exampleDescription.textContent = `示例加载失败：${error.message}`;
    }
  }
}

function findExampleByInputFilename(inputFilename) {
  return state.exampleCache.find((item) => item.input_filename === inputFilename) || null;
}

async function ensureExampleDetailLoaded(exampleId) {
  const existing = state.exampleDetailCache[exampleId];
  if (existing?.status === "loaded") {
    return existing.payload;
  }
  if (existing?.status === "loading") {
    return null;
  }
  state.exampleDetailCache[exampleId] = { status: "loading" };
  try {
    const payload = await fetchJson(`/api/examples/${encodeURIComponent(exampleId)}`);
    const normalized = {
      input_filename: payload.input_filename,
      text_content: payload.text_content || "",
      character_count: String(payload.text_content || "").length,
    };
    state.exampleDetailCache[exampleId] = { status: "loaded", payload: normalized };
    return normalized;
  } catch (error) {
    state.exampleDetailCache[exampleId] = { status: "error", error: error.message };
    return null;
  }
}

async function previewExampleRun() {
  const example = state.exampleCache[0];
  if (!example) {
    setFormStatus("当前没有可用示例。", "tone-error");
    return;
  }
  setActionBusy(true);
  setFormStatus(`正在加载预计算样例：${example.title}...`);
  try {
    const payload = await fetchJson(`/api/examples/${encodeURIComponent(example.id)}/preview-run`, {
      method: "POST",
    });
    setFormStatus("已加载预计算样例结果。当前展示不消耗你填写的 endpoint / Key。");
    await refreshRuns();
    await loadRun(payload.id);
  } catch (error) {
    setFormStatus(`样例加载失败：${error.message}`, "tone-error");
  } finally {
    setActionBusy(false);
  }
}

async function startExampleRun() {
  const example = state.exampleCache[0];
  if (!example) {
    setFormStatus("当前没有可用示例。", "tone-error");
    return;
  }
  const formData = collectRunFormData();
  formData.delete("file");
  setActionBusy(true);
  setFormStatus(`正在按当前配置试跑样例：${example.title}...`);
  try {
    const payload = await fetchJson(`/api/examples/${encodeURIComponent(example.id)}/runs`, {
      method: "POST",
      body: formData,
    });
    setFormStatus("样例试跑任务已创建，开始轮询。");
    await refreshRuns();
    await loadRun(payload.id);
  } catch (error) {
    setFormStatus(`样例试跑失败：${error.message}`, "tone-error");
  } finally {
    setActionBusy(false);
  }
}

function setWorkspaceTab(tabName) {
  state.activeWorkspaceTab = tabName;
  for (const tab of elements.workspaceTabs) {
    tab.classList.toggle("is-active", tab.dataset.tabTarget === tabName);
  }
  for (const panel of elements.workspacePanels) {
    panel.classList.toggle("hidden", panel.dataset.tabPanel !== tabName);
  }
}

function setSidebarTab(tabName) {
  state.activeSidebarTab = tabName;
  for (const tab of elements.sidebarTabs) {
    tab.classList.toggle("is-active", tab.dataset.sidebarTarget === tabName);
  }
  for (const panel of elements.sidebarPanels) {
    panel.classList.toggle("hidden", panel.dataset.sidebarPanel !== tabName);
  }
}

function setSourceTab(tabName) {
  state.activeSourceTab = tabName;
  for (const tab of elements.sourceTabButtons) {
    tab.classList.toggle("is-active", tab.dataset.sourceTabTarget === tabName);
  }
  renderSourcePanel(state.activeRunDetail);
  if (tabName === "full" && state.activeRunId) {
    void ensureSourceTextLoaded(state.activeRunId);
  }
}

function setOutputTab(tabName) {
  state.activeOutputTab = tabName;
  for (const tab of elements.outputTabButtons) {
    tab.classList.toggle("is-active", tab.dataset.outputTabTarget === tabName);
  }
  renderOutputPanel(state.activeRunDetail);
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
          <span class="label">${escapeHtml(formatRunStatus(run.status))}</span>
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
    elements.benchmarkList.innerHTML = '<p class="hint">暂无对照评测报告。</p>';
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
          <span class="label">${escapeHtml(formatBenchmarkWinner(item.winner))}</span>
          <strong>${escapeHtml(item.dataset_name)} / ${escapeHtml(item.case_name)}</strong>
          <p>前文 ${escapeHtml(item.prefix_chapter_count)} 章 → 目标第 ${escapeHtml(item.target_chapter_number)} 章</p>
          <p>置信度 ${escapeHtml(Number(item.confidence).toFixed(2))}</p>
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
    `案例：${detail.case_name}`,
    `结果：${formatBenchmarkWinner(detail.winner)}`,
    `置信度：${Number(detail.confidence).toFixed(2)}`,
    `系统版分数：${Number(detail.system_score).toFixed(2)}`,
    `基线版分数：${Number(detail.baseline_score).toFixed(2)}`,
    `系统版摘要：${detail.system_summary || "-"}`,
    `基线版摘要：${detail.baseline_summary || "-"}`,
    `系统版优点：${detail.system_strengths?.length ? detail.system_strengths.join("；") : "-"}`,
    `基线版优点：${detail.baseline_strengths?.length ? detail.baseline_strengths.join("；") : "-"}`,
    `系统版不足：${detail.system_weaknesses?.length ? detail.system_weaknesses.join("；") : "-"}`,
    `基线版不足：${detail.baseline_weaknesses?.length ? detail.baseline_weaknesses.join("；") : "-"}`,
    `系统版耗时：${formatDuration(detail.system_elapsed_seconds)}`,
    `基线版耗时：${formatDuration(detail.baseline_elapsed_seconds)}`,
    `总成本：${formatCurrency(detail.total_cost_usd)}`,
    `总 Token 数：${formatNumber(detail.total_tokens)}`,
    `系统版输出：${detail.system_output_path}`,
    `基线版输出：${detail.baseline_output_path}`,
    `参考正文：${detail.reference_path}`,
    `JSON 报告：${detail.report_json_path}`,
    `Markdown 报告：${detail.report_markdown_path}`,
    `评审理由：`,
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
    ["运行清单", paths?.manifest],
    ["第一阶段快照", paths?.stage1_snapshot],
    ["世界模型", paths?.world_model],
    ["世界设定参考", paths?.lorebook],
    ["已选参考片段", paths?.selected_references],
    ["作品 skill", paths?.work_skill],
    ["人物走向选项", paths?.arc_options],
    ["已选人物走向", paths?.selected_arc],
    ["复活诊断", paths?.revival_diagnosis],
    ["盲看挑战", paths?.blind_challenge],
    ["最新提纲草稿", paths?.latest_skeleton],
    ["最新章节目标", paths?.latest_chapter_brief],
    ["最新章节评测", paths?.latest_chapter_evaluation],
    ["最新续写候选", paths?.latest_draft],
    ["最新输出正文", paths?.latest_output],
    ["故事图谱", paths?.story_graph],
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
          <strong>候选 ${index + 1}</strong>
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

function renderArcList(run) {
  elements.arcList.innerHTML = "";
  const directorOptions = run.arc_options?.options || [];
  if (directorOptions.length) {
    const selectedId = run.selected_arc?.selected_option_id;
    const canSelect = run.status === "awaiting_arc_selection";
    elements.arcList.innerHTML = directorOptions
      .map((arc) => {
        const isSelected = selectedId === arc.id;
        const buttonHtml = canSelect
          ? `<button type="button" class="utility-button arc-select-button" data-arc-id="${escapeHtml(arc.id)}">选择</button>`
          : isSelected
            ? `<span class="status-pill">已选择</span>`
            : "";
        return `
          <div class="chapter-item ${isSelected ? "is-selected" : ""}">
            <strong>${escapeHtml(arc.title)} · ${escapeHtml(arc.id)}</strong>
            <div class="chapter-meta">
              <span>${escapeHtml((arc.character_focus || []).join("、") || "人物未指定")}</span>
              <span>${escapeHtml((arc.risk_flags || []).join("；") || "无风险标记")}</span>
            </div>
            <span>${escapeHtml(arc.emotional_direction || "-")}</span>
            ${
              arc.consequences?.length
                ? `<span>${escapeHtml(arc.consequences.join("；"))}</span>`
                : ""
            }
            ${buttonHtml}
          </div>
        `;
      })
      .join("");
    return;
  }

  const arcs = run.arc_outlines || [];
  if (!arcs?.length) {
    elements.arcList.innerHTML = '<div class="chapter-item"><strong>当前没有故事走向规划</strong></div>';
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

function renderBlindChallenge(run) {
  if (!elements.blindChallenge) return;
  const challenge = run.blind_challenge;
  if (!challenge) {
    elements.blindChallenge.innerHTML = '<div class="thread-item"><strong>生成章节后出现盲看片段</strong></div>';
    return;
  }
  const ratings = challenge.ratings || {};
  const ratedText = challenge.rated_at ? `<span>已评分：${escapeHtml(challenge.rated_at)}</span>` : "";
  elements.blindChallenge.innerHTML = `
    <div class="thread-item">
      <strong>${escapeHtml(challenge.excerpt_char_count || 0)} 字盲看片段</strong>
      <span>${escapeHtml((challenge.excerpt_text || "").slice(0, 220))}${(challenge.excerpt_text || "").length > 220 ? "..." : ""}</span>
      ${ratedText}
      <div class="field-grid">
        <label class="field">
          <span>声口</span>
          <input name="voice_match_score" type="number" min="1" max="5" value="${escapeHtml(ratings.voice_match_score || "")}" />
        </label>
        <label class="field">
          <span>节奏</span>
          <input name="rhythm_match_score" type="number" min="1" max="5" value="${escapeHtml(ratings.rhythm_match_score || "")}" />
        </label>
        <label class="field">
          <span>人物</span>
          <input name="character_voice_score" type="number" min="1" max="5" value="${escapeHtml(ratings.character_voice_score || "")}" />
        </label>
      </div>
      <label class="field">
        <span>备注</span>
        <textarea name="blind_notes" rows="2">${escapeHtml(ratings.notes || challenge.notes || "")}</textarea>
      </label>
      <button type="button" class="utility-button" id="blind-rating-submit">保存盲测评分</button>
    </div>
  `;
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
          <strong>第 ${escapeHtml(chapter.chapter_number)} 章 · ${escapeHtml(formatRunStatus(chapter.status))}</strong>
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

function renderSourcePanel(run) {
  const isFullText = state.activeSourceTab === "full";
  for (const tab of elements.sourceTabButtons) {
    tab.classList.toggle("is-active", tab.dataset.sourceTabTarget === state.activeSourceTab);
  }

  if (!run) {
    elements.sourcePreviewLabel.textContent = "原文断点";
    elements.sourcePreviewMeta.textContent = "仅展示当前衔接最相关的原文片段";
    elements.sourcePreview.classList.remove("markdown-preview-scrollable");
    elements.sourcePreview.innerHTML = renderMarkdownPreview(null);
    return;
  }

  if (!isFullText) {
    elements.sourcePreviewLabel.textContent = run.latest_source_preview_label || "原文断点";
    elements.sourcePreviewMeta.textContent = "仅展示当前衔接最相关的原文片段";
    elements.sourcePreview.classList.remove("markdown-preview-scrollable");
    elements.sourcePreview.innerHTML = renderMarkdownPreview(run.latest_source_preview);
    return;
  }

  elements.sourcePreviewLabel.textContent = "原始正文";
  elements.sourcePreview.classList.add("markdown-preview-scrollable");
  const entry = state.sourceTextCache[run.id];
  if (!entry || entry.status === "loading") {
    elements.sourcePreviewMeta.textContent = "正在加载原始正文...";
    elements.sourcePreview.innerHTML = '<p class="markdown-empty">正在加载原始正文...</p>';
    if (!entry) {
      void ensureSourceTextLoaded(run.id);
    }
    return;
  }
  if (entry.status === "error") {
    elements.sourcePreviewMeta.textContent = "原始正文加载失败";
    elements.sourcePreview.innerHTML = `<p class="markdown-empty">${escapeHtml(entry.error || "加载失败")}</p>`;
    return;
  }
  elements.sourcePreviewMeta.textContent = `${entry.payload.input_filename} · ${formatNumber(entry.payload.character_count)} 字`;
  elements.sourcePreview.innerHTML = renderMarkdownPreview(entry.payload.text_content);
}

function renderOutputNote(noteBody) {
  if (!noteBody) return "";
  return `
    <section class="output-note">
      <div class="stitched-preview-heading">
        <p class="label">模型附注</p>
        <span class="stitched-preview-note">原始输出里带有说明文字，已与续写正文分开展示</span>
      </div>
      <div class="markdown-preview markdown-preview-note">${renderMarkdownPreview(noteBody)}</div>
    </section>
  `;
}

function renderOutputPanel(run) {
  for (const tab of elements.outputTabButtons) {
    tab.classList.toggle("is-active", tab.dataset.outputTabTarget === state.activeOutputTab);
  }

  if (!run) {
    elements.outputPreviewLabel.textContent = "AI 生成的续写章节";
    elements.outputPreviewMeta.textContent = "按连续阅读方式展示：先原文断点，再接 AI 生成章节";
    elements.outputPath.textContent = "-";
    elements.outputPath.title = "";
    elements.outputPreview.innerHTML = '<div class="markdown-preview"><p class="markdown-empty">暂无正文预览</p></div>';
    return;
  }

  const latestOutputPath =
    run.artifact_paths?.latest_output ||
    (Array.isArray(run.output_paths) && run.output_paths.length ? run.output_paths[run.output_paths.length - 1] : "-");
  const { body, noteBody } = splitOutputMarkdown(run.latest_output_preview);
  const outputBody = body || run.latest_output_preview;
  const sourceLabel = run.latest_source_preview_label || "原文断点";
  const sourcePreviewHtml = renderMarkdownPreview(run.latest_source_preview);
  const outputPreviewHtml = renderMarkdownPreview(outputBody);
  const noteHtml = renderOutputNote(noteBody);

  elements.outputPath.textContent = latestOutputPath;
  elements.outputPath.title = latestOutputPath;
  elements.outputPreviewLabel.textContent = "AI 生成的续写章节";

  if (state.activeOutputTab === "chapter") {
    elements.outputPreviewMeta.textContent = "仅展示 AI 新生成章节正文，便于单独评估文风、节奏和信息推进。";
    elements.outputPreview.innerHTML = `
      <section class="stitched-preview-section stitched-preview-section-output stitched-preview-section-single">
        <div class="stitched-preview-heading">
          <p class="label">续写章节</p>
          <span class="stitched-preview-note">以下内容为模型新生成的章节正文</span>
        </div>
        <div class="markdown-preview">${outputPreviewHtml}</div>
      </section>
      ${noteHtml}
    `;
    return;
  }

  elements.outputPreviewMeta.textContent = "按连续阅读方式展示：先原文断点 / 上文衔接，再接 AI 生成章节。";
  elements.outputPreview.innerHTML = `
    <section class="stitched-preview-section stitched-preview-section-source">
      <div class="stitched-preview-heading">
        <p class="label">${escapeHtml(sourceLabel)}</p>
        <span class="stitched-preview-note">先看进入续写前的原文衔接内容</span>
      </div>
      <div class="markdown-preview markdown-preview-source">${sourcePreviewHtml}</div>
    </section>
    <div class="stitched-preview-divider" aria-hidden="true">
      <span>AI 从这里开始续写</span>
      <small>先看上文断点，再判断 AI 是否顺着原文继续推进</small>
    </div>
    <section class="stitched-preview-section stitched-preview-section-output">
      <div class="stitched-preview-heading">
        <p class="label">续写章节</p>
        <span class="stitched-preview-note">以下内容为模型新生成的章节正文</span>
      </div>
      <div class="markdown-preview">${outputPreviewHtml}</div>
    </section>
    ${noteHtml}
  `;
}

async function ensureSourceTextLoaded(runId) {
  const existing = state.sourceTextCache[runId];
  if (existing?.status === "loading" || existing?.status === "loaded") {
    return;
  }
  const run =
    (state.activeRunId === runId && state.activeRunDetail) ||
    state.runCache.find((item) => item.id === runId) ||
    null;
  state.sourceTextCache[runId] = { status: "loading" };
  if (state.activeRunId === runId) {
    renderSourcePanel(state.activeRunDetail);
  }
  try {
    const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}/source-text`);
    state.sourceTextCache[runId] = { status: "loaded", payload };
  } catch (error) {
    const fallbackExample = run ? findExampleByInputFilename(run.input_filename) : null;
    if (fallbackExample) {
      const fallbackPayload = await ensureExampleDetailLoaded(fallbackExample.id);
      if (fallbackPayload) {
        state.sourceTextCache[runId] = { status: "loaded", payload: fallbackPayload };
      } else {
        state.sourceTextCache[runId] = { status: "error", error: "内置样例原始正文加载失败。" };
      }
    } else {
      const normalizedError =
        error.message === "Not Found"
          ? "当前服务还没有原始正文接口，重启 Web 服务后再试。"
          : error.message;
      state.sourceTextCache[runId] = { status: "error", error: normalizedError };
    }
  }
  if (state.activeRunId === runId) {
    renderSourcePanel(state.activeRunDetail);
  }
}

function renderRun(run) {
  state.activeRunDetail = run;
  elements.emptyState.classList.add("hidden");
  elements.runView.classList.remove("hidden");

  elements.runId.textContent = run.id;
  elements.runSession.textContent = run.session_name;
  elements.runStatus.textContent = formatRunStatus(run.status);
  elements.runId.title = run.id;
  elements.runSession.title = run.session_name;
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

  elements.modelSummary.textContent = formatModelSummary(run.request);
  elements.styleSummary.textContent = formatStyleSummary(run.style_profile);
  elements.storySummary.textContent = formatStorySummary(run.story_state);
  elements.workSkillSummary.textContent = formatWorkSkillSummary(run.work_skill);
  elements.worldSummary.textContent = formatWorldSummary(run.world_model);
  elements.lorebookSummary.textContent = formatLorebookSummary(run.lorebook);
  elements.goalSummary.textContent = run.latest_chapter_goal || "-";
  elements.briefSummary.textContent = formatBriefSummary(run.latest_chapter_brief);
  elements.evaluationSummary.textContent = formatEvaluationSummary(run.latest_chapter_evaluation);
  elements.qualitySummary.textContent = formatQualitySummary(run.latest_quality_report);
  elements.consistencySummary.textContent = formatConsistencySummary(run.latest_consistency_report);
  elements.revivalDiagnosisSummary.textContent = formatRevivalDiagnosis(run.revival_diagnosis);
  renderSourcePanel(run);
  renderOutputPanel(run);

  renderArtifacts(run.artifact_paths);
  renderCandidatePaths(elements.skeletonCandidateList, run.latest_skeleton_candidate_paths, "暂无提纲草稿");
  renderCandidatePaths(elements.draftCandidateList, run.latest_draft_candidate_paths, "暂无续写候选");
  renderReferences(run.selected_references);
  renderArcList(run);
  renderBlindChallenge(run);
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

async function loadRuntimeConfig() {
  const config = await fetchJson("/api/config");
  applyRuntimeConfig(config);
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
  if (isLiveRunStatus(run.status)) {
    startPolling(runId);
  } else {
    stopPolling();
  }
}

async function selectArcOption(optionId) {
  if (!state.activeRunId || !optionId) return;
  setFormStatus("正在提交人物走向...");
  const payload = await fetchJson(`/api/revival/runs/${encodeURIComponent(state.activeRunId)}/arc-selection`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      selected_option_id: optionId,
      arc_options_digest: state.activeRunDetail?.arc_options_digest || null,
    }),
  });
  setFormStatus("人物走向已选择，开始生成章节。");
  await refreshRuns();
  await loadRun(payload.id);
  startPolling(payload.id);
}

async function submitBlindChallengeRating() {
  if (!state.activeRunId || !elements.blindChallenge) return;
  const numberValue = (name) => {
    const value = elements.blindChallenge.querySelector(`[name="${name}"]`)?.value;
    return value ? Number(value) : null;
  };
  const notes = elements.blindChallenge.querySelector('[name="blind_notes"]')?.value || "";
  await fetchJson(`/api/revival/runs/${encodeURIComponent(state.activeRunId)}/blind-challenge`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      voice_match_score: numberValue("voice_match_score"),
      rhythm_match_score: numberValue("rhythm_match_score"),
      character_voice_score: numberValue("character_voice_score"),
      notes,
    }),
  });
  setFormStatus("盲测评分已保存。");
  await loadRun(state.activeRunId);
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
      if (!isLiveRunStatus(run.status)) {
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

if (elements.arcList) {
  elements.arcList.addEventListener("click", async (event) => {
    const button = event.target.closest(".arc-select-button");
    if (!button) return;
    button.disabled = true;
    try {
      await selectArcOption(button.dataset.arcId);
    } catch (error) {
      setFormStatus(`选择失败：${error.message}`, "tone-error");
      button.disabled = false;
    }
  });
}

if (elements.blindChallenge) {
  elements.blindChallenge.addEventListener("click", async (event) => {
    if (event.target.id !== "blind-rating-submit") return;
    event.target.disabled = true;
    try {
      await submitBlindChallengeRating();
    } catch (error) {
      setFormStatus(`保存评分失败：${error.message}`, "tone-error");
      event.target.disabled = false;
    }
  });
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = collectRunFormData();
  setActionBusy(true);
  setFormStatus("正在创建任务...");

  try {
    const payload = await fetchJson("/api/revival/runs", {
      method: "POST",
      body: formData,
    });
    setFormStatus("分析任务已创建，生成 3 条人物走向后会等待选择。");
    await refreshRuns();
    await loadRun(payload.id);
  } catch (error) {
    setFormStatus(`提交失败：${error.message}`, "tone-error");
  } finally {
    setActionBusy(false);
  }
});

window.addEventListener("load", async () => {
  try {
    for (const tab of elements.workspaceTabs) {
      tab.addEventListener("click", () => setWorkspaceTab(tab.dataset.tabTarget));
    }
    for (const tab of elements.sourceTabButtons) {
      tab.addEventListener("click", () => setSourceTab(tab.dataset.sourceTabTarget));
    }
    for (const tab of elements.outputTabButtons) {
      tab.addEventListener("click", () => setOutputTab(tab.dataset.outputTabTarget));
    }
    for (const tab of elements.sidebarTabs) {
      tab.addEventListener("click", () => setSidebarTab(tab.dataset.sidebarTarget));
    }
    if (elements.tryExampleButton) {
      elements.tryExampleButton.addEventListener("click", previewExampleRun);
    }
    if (elements.loadExampleButton) {
      elements.loadExampleButton.addEventListener("click", startExampleRun);
    }
    if (elements.emptyExampleButton) {
      elements.emptyExampleButton.addEventListener("click", previewExampleRun);
    }
    if (elements.emptyFillExampleButton) {
      elements.emptyFillExampleButton.addEventListener("click", startExampleRun);
    }
    if (elements.resetModelsButton) {
      elements.resetModelsButton.addEventListener("click", resetModelInputs);
    }
    if (elements.clearApiConfigButton) {
      elements.clearApiConfigButton.addEventListener("click", clearApiConfigInputs);
    }
    if (elements.openAdvancedOptionsButton) {
      elements.openAdvancedOptionsButton.addEventListener("click", () => openAdvancedOptions());
    }
    window.addEventListener("hashchange", applyStudioHashIntent);
    setWorkspaceTab(state.activeWorkspaceTab);
    setSourceTab(state.activeSourceTab);
    setOutputTab(state.activeOutputTab);
    setSidebarTab(state.activeSidebarTab);
    await loadRuntimeConfig();
    clearApiConfigInputs();
    await loadExamples();
    await refreshRuns({ autoSelect: true });
    await refreshBenchmarks();
    applyStudioHashIntent();
  } catch (error) {
    setFormStatus(`初始化失败：${error.message}`, "tone-error");
  }
});
