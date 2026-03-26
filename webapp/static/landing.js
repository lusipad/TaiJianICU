const benchmarkContainer = document.getElementById("landing-benchmark-list");
const revealNodes = Array.from(document.querySelectorAll("[data-reveal]"));

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatCurrency(value) {
  return `$${Number(value || 0).toFixed(6)}`;
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

async function fetchJson(url) {
  const response = await fetch(url);
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(payload.detail || `请求失败：${response.status}`);
  }
  return payload;
}

async function renderBenchmarks() {
  try {
    const items = await fetchJson("/api/benchmarks");
    if (!items.length) {
      benchmarkContainer.innerHTML = '<p class="hint">当前还没有对照评测报告。</p>';
      return;
    }

    const details = await Promise.all(
      items.slice(0, 2).map((item) =>
        fetchJson(`/api/benchmarks/${encodeURIComponent(item.dataset_name)}/${encodeURIComponent(item.case_name)}`)
      )
    );

    benchmarkContainer.innerHTML = details
      .map(
        (detail) => `
          <article class="landing-benchmark-card">
            <div class="showcase-head">
              <p class="label">${escapeHtml(detail.dataset_name)}</p>
              <strong>${escapeHtml(detail.case_name)}</strong>
            </div>
            <div class="benchmark-meta-row">
              <span>结果 ${escapeHtml(formatBenchmarkWinner(detail.winner))}</span>
              <span>置信度 ${escapeHtml(Number(detail.confidence).toFixed(2))}</span>
              <span>成本 ${escapeHtml(formatCurrency(detail.total_cost_usd))}</span>
            </div>
            <div class="benchmark-score-strip">
              <div>
                <span class="showcase-label">系统版</span>
                <strong>${escapeHtml(Number(detail.system_score).toFixed(2))}</strong>
              </div>
              <div>
                <span class="showcase-label">基线版</span>
                <strong>${escapeHtml(Number(detail.baseline_score).toFixed(2))}</strong>
              </div>
            </div>
            <p class="benchmark-summary">${escapeHtml(detail.system_summary || "-")}</p>
            <p class="benchmark-footnote">仅展示评测摘要，不直接展示外部作品正文。</p>
          </article>
        `
      )
      .join("");
  } catch (error) {
    benchmarkContainer.innerHTML = `<p class="hint tone-error">加载失败：${escapeHtml(error.message)}</p>`;
  }
}

function setupReveal() {
  if (!revealNodes.length) return;
  const observer = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      }
    },
    { threshold: 0.18 }
  );
  for (const node of revealNodes) {
    observer.observe(node);
  }
}

window.addEventListener("load", () => {
  setupReveal();
  renderBenchmarks();
});
