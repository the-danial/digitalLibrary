(function () {
  const THEME_KEY = "sandbox_theme";
  const themes = ["default", "cyber", "minimal"];

  function setTheme(t) {
    const html = document.documentElement;
    html.setAttribute("data-theme", t);
    localStorage.setItem(THEME_KEY, t);
    toast(`تم فعال شد: ${t === "default" ? "پیش‌فرض" : t}`);
  }

  function getTheme() {
    return localStorage.getItem(THEME_KEY) || "default";
  }

  function toast(msg) {
    const el = document.getElementById("toast");
    if (!el) return;
    el.textContent = msg;
    el.classList.add("show");
    clearTimeout(window.__toastTimer);
    window.__toastTimer = setTimeout(() => el.classList.remove("show"), 1400);
  }

  function animateNumber(el, to, duration = 420) {
    const from = Number(el.dataset._num || el.textContent || 0) || 0;
    const start = performance.now();

    function tick(now) {
      const p = Math.min(1, (now - start) / duration);
      const val = Math.round(from + (to - from) * (1 - Math.pow(1 - p, 3)));
      el.textContent = val.toString();
      if (p < 1) requestAnimationFrame(tick);
      else el.dataset._num = String(to);
    }
    requestAnimationFrame(tick);
  }

  function initNumbers() {
    document.querySelectorAll("[data-animate-number]").forEach((el) => {
      const v = Number(el.textContent || 0) || 0;
      el.dataset._num = String(v);
    });
  }

  function initStatBars() {
    // Expect stats are 0..100 for rep/morale; budget can be any -> normalize softly
    const init = window.__SANDBOX_INIT__ || { budget: 0, rep: 0, morale: 0 };

    const rep = clamp(init.rep, 0, 100);
    const morale = clamp(init.morale, 0, 100);

    // Budget normalization: clamp between 0..2000 (adjust if you want)
    const budgetNorm = (clamp(init.budget, 0, 2000) / 2000) * 100;

    document.querySelectorAll("[data-fill-by]").forEach((bar) => {
      const kind = bar.getAttribute("data-fill-by");
      let w = 50;
      if (kind === "rep") w = rep;
      if (kind === "morale") w = morale;
      if (kind === "budget") w = budgetNorm;
      bar.style.width = `${clamp(w, 0, 100)}%`;
    });
  }

  function clamp(x, a, b) {
    return Math.max(a, Math.min(b, x));
  }

  function initChoiceHoverPreview() {
    const choices = document.querySelectorAll(".choice");
    if (!choices.length) return;

    choices.forEach((btn) => {
      btn.addEventListener("mouseenter", () => {
        const db = btn.getAttribute("data-delta-budget");
        const dr = btn.getAttribute("data-delta-rep");
        const dm = btn.getAttribute("data-delta-morale");

        const parts = [];
        if (db) parts.push(`بودجه: ${formatDelta(db)}`);
        if (dr) parts.push(`شهرت: ${formatDelta(dr)}`);
        if (dm) parts.push(`روحیه: ${formatDelta(dm)}`);

        if (parts.length) toast(parts.join("  •  "));
      });
    });

    function formatDelta(x) {
      const n = Number(x);
      if (Number.isNaN(n)) return x;
      return `${n >= 0 ? "+" : ""}${n}`;
    }
  }

  function initThemeBtn() {
    const btn = document.getElementById("themeBtn");
    if (!btn) return;

    // apply stored theme on load
    const current = getTheme();
    document.documentElement.setAttribute("data-theme", current);

    btn.addEventListener("click", () => {
      const cur =
        document.documentElement.getAttribute("data-theme") || "default";
      const idx = themes.indexOf(cur);
      const next = themes[(idx + 1) % themes.length];
      setTheme(next);
    });
  }

  function initAnimatedStats() {
    // If you ever update stats dynamically later, you can call window.SandboxUI.updateStats(...)
    window.SandboxUI = window.SandboxUI || {};
    window.SandboxUI.updateStats = (next) => {
      const map = {
        budget: next.budget,
        reputation: next.rep ?? next.reputation,
        morale: next.morale,
        score: next.score,
      };

      document.querySelectorAll("[data-animate-number]").forEach((el) => {
        // Heuristic: map by surrounding labels is hard; this is for future upgrades.
        // For now, we don’t auto-guess.
      });

      initStatBars();
    };
  }

  // Boot
  document.addEventListener("DOMContentLoaded", () => {
    initThemeBtn();
    initNumbers();
    initStatBars();
    initChoiceHoverPreview();
    initAnimatedStats();
    function initChoiceHoverPreview() {
      const choices = document.querySelectorAll(".choice");
      if (!choices.length) return;

      choices.forEach((btn) => {
        btn.addEventListener("mouseenter", () => {
          const db = btn.getAttribute("data-delta-budget");
          const dr = btn.getAttribute("data-delta-rep");
          const dm = btn.getAttribute("data-delta-morale");

          const parts = [];
          if (db && db !== "") parts.push(`بودجه: ${formatDelta(db)}`);
          if (dr && dr !== "") parts.push(`شهرت: ${formatDelta(dr)}`);
          if (dm && dm !== "") parts.push(`روحیه: ${formatDelta(dm)}`);

          if (parts.length) showToast(parts.join("  •  "));
        });
      });

      function formatDelta(x) {
        const n = Number(x);
        if (Number.isNaN(n)) return x;
        return `${n >= 0 ? "+" : ""}${n}`;
      }
    }

    function showToast(msg) {
      const el = document.getElementById("toast");
      if (!el) return;
      el.textContent = msg;
      el.classList.add("show");
      clearTimeout(window.__toastTimer);
      window.__toastTimer = setTimeout(() => el.classList.remove("show"), 1400);
    }
  });
})();
