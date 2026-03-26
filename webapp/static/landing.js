const benchmarkContainer = document.getElementById("landing-benchmark-list");
const revealNodes = Array.from(document.querySelectorAll("[data-reveal]"));
const nav = document.getElementById("landing-nav");

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
  if (!benchmarkContainer) return;
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

    const lead = details[0];

    benchmarkContainer.innerHTML = `
      <section class="bench-shell">
        <div class="bench-table">
          <div class="bench-row bench-row-head">
            <span>案例</span>
            <span>系统版</span>
            <span>基线</span>
            <span>结论</span>
          </div>
          ${details
            .map(
              (detail) => `
                <div class="bench-row">
                  <div class="bench-row-label">
                    <strong>${escapeHtml(detail.case_name)}</strong>
                    <span>${escapeHtml(detail.system_summary || "-")}</span>
                  </div>
                  <div class="bench-row-score winner">${escapeHtml(Number(detail.system_score).toFixed(2))}</div>
                  <div class="bench-row-score">${escapeHtml(Number(detail.baseline_score).toFixed(2))}</div>
                  <div class="bench-row-verdict">
                    <strong>${escapeHtml(formatBenchmarkWinner(detail.winner))}</strong>
                    <span>置信度 ${escapeHtml(Number(detail.confidence).toFixed(2))}</span>
                  </div>
                </div>
              `
            )
            .join("")}
        </div>
        <aside class="bench-summary-card">
          <p class="section-kicker">动态摘要</p>
          <strong>${escapeHtml(lead.dataset_name)} / ${escapeHtml(lead.case_name)}</strong>
          <p>${escapeHtml(lead.system_summary || "-")}</p>
          <div class="bench-summary-metrics">
            <span>系统版 ${escapeHtml(Number(lead.system_score).toFixed(2))}</span>
            <span>基线 ${escapeHtml(Number(lead.baseline_score).toFixed(2))}</span>
            <span>成本 ${escapeHtml(formatCurrency(lead.total_cost_usd))}</span>
          </div>
          <p class="bench-footnote">仅展示摘要与分数，不直接展示外部作品正文。</p>
        </aside>
      </section>
    `;
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
  if (nav) {
    const toggleNav = () => nav.classList.toggle("scrolled", window.scrollY > 24);
    toggleNav();
    window.addEventListener("scroll", toggleNav, { passive: true });
  }
  setupReveal();
  renderBenchmarks();
});
