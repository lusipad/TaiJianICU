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

function formatScore(value) {
  if (value == null || Number.isNaN(Number(value))) return "-";
  return Number(value).toFixed(2);
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
    const showcase = await fetchJson("/api/showcase");
    if (!showcase) {
      benchmarkContainer.innerHTML = '<p class="hint">当前公开样例还没生成，请先去 Studio 试跑内置原创样例。</p>';
      return;
    }

    benchmarkContainer.innerHTML = `
      <section class="bench-shell proof-shell">
        <div class="proof-main">
          <div class="proof-grid">
            <article class="proof-card">
              <p class="section-kicker">原文断点</p>
              <strong>${escapeHtml(showcase.source_label)}</strong>
              <pre class="showcase-prose">${escapeHtml(showcase.source_excerpt || "-")}</pre>
            </article>
            <article class="proof-card proof-card-accent">
              <p class="section-kicker">AI 续写</p>
              <strong>${escapeHtml(showcase.output_label)}</strong>
              <pre class="showcase-prose showcase-prose-ai">${escapeHtml(showcase.output_excerpt || "-")}</pre>
            </article>
          </div>
        </div>
        <aside class="bench-summary-card proof-summary-card">
          <p class="section-kicker">质检结论</p>
          <strong>${escapeHtml(showcase.title)}</strong>
          <p>${escapeHtml(showcase.evaluation_summary || "当前没有可展示的质检摘要。")}</p>
          <div class="bench-summary-metrics proof-summary-metrics">
            <span>连贯 ${escapeHtml(formatScore(showcase.continuity_score))}</span>
            <span>人物 ${escapeHtml(formatScore(showcase.character_score))}</span>
            <span>世界 ${escapeHtml(formatScore(showcase.world_consistency_score))}</span>
            <span>新意 ${escapeHtml(formatScore(showcase.novelty_score))}</span>
            <span>推进 ${escapeHtml(formatScore(showcase.arc_progress_score))}</span>
          </div>
          <div class="proof-note">
            <p class="showcase-label">章节目标</p>
            <p>${escapeHtml(showcase.chapter_goal || "-")}</p>
          </div>
          <p class="bench-footnote">公开实证只展示原创或公版文本短片段；既给你看文字，也给你看分数。</p>
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
