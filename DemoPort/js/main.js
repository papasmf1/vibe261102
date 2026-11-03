(() => {
  const root = document.documentElement;

  // ===== Theme (light / dark) =====
  const THEME_KEY = "demoport-theme";
  const themeToggle = document.querySelector(".theme-toggle");
  const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

  const getSavedTheme = () => {
    try { return localStorage.getItem(THEME_KEY); } catch { return null; }
  };

  const applyTheme = (theme) => {
    root.dataset.theme = theme;
    themeToggle.setAttribute("aria-label", theme === "dark" ? "라이트 모드로 전환" : "다크 모드로 전환");
  };

  applyTheme(getSavedTheme() || (systemDark.matches ? "dark" : "light"));

  systemDark.addEventListener("change", (e) => {
    if (!getSavedTheme()) applyTheme(e.matches ? "dark" : "light");
  });

  themeToggle.addEventListener("click", () => {
    const next = root.dataset.theme === "dark" ? "light" : "dark";
    applyTheme(next);
    try { localStorage.setItem(THEME_KEY, next); } catch { /* ignore */ }
  });

  // ===== Mobile nav =====
  const navToggle = document.querySelector(".nav-toggle");
  const navMenu = document.getElementById("nav-menu");

  const setMenu = (open) => {
    navMenu.classList.toggle("open", open);
    navToggle.setAttribute("aria-expanded", String(open));
    navToggle.setAttribute("aria-label", open ? "메뉴 닫기" : "메뉴 열기");
  };

  navToggle.addEventListener("click", () => setMenu(!navMenu.classList.contains("open")));
  navMenu.addEventListener("click", (e) => {
    if (e.target.closest("a")) setMenu(false);
  });

  // ===== Projects =====
  const grid = document.getElementById("projects-grid");
  const projects = window.PROJECTS || [];
  const LINK_LABELS = { github: "GitHub", demo: "Demo", appstore: "App Store" };

  const escapeHtml = (str) =>
    String(str).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  const renderProjects = (filter) => {
    const list = filter === "all" ? projects : projects.filter((p) => p.category === filter);
    grid.innerHTML = list.map((p) => `
      <article class="project-card">
        <div class="project-thumb thumb-${p.category}" aria-hidden="true">${p.icon || "💻"}</div>
        <div class="project-body">
          <h3>${escapeHtml(p.title)}</h3>
          <p>${escapeHtml(p.description)}</p>
          <ul class="project-tags">${p.tags.map((t) => `<li>${escapeHtml(t)}</li>`).join("")}</ul>
          <div class="project-links">
            ${Object.entries(p.links || {})
              .map(([key, url]) => `<a href="${escapeHtml(url)}" target="_blank" rel="noopener">${LINK_LABELS[key] || key} →</a>`)
              .join("")}
          </div>
        </div>
      </article>`).join("");
  };

  document.querySelectorAll(".filter-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach((b) => {
        b.classList.toggle("active", b === btn);
        b.setAttribute("aria-pressed", String(b === btn));
      });
      renderProjects(btn.dataset.filter);
    });
  });

  renderProjects("all");

  // ===== Copy email =====
  const toast = document.querySelector(".copy-toast");
  document.querySelectorAll(".copy-btn").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const text = btn.dataset.copy;
      try {
        await navigator.clipboard.writeText(text);
        toast.textContent = "이메일 주소가 복사되었습니다!";
      } catch {
        toast.textContent = `복사에 실패했습니다. 직접 복사해 주세요: ${text}`;
      }
      clearTimeout(btn._timer);
      btn._timer = setTimeout(() => { toast.textContent = ""; }, 2500);
    });
  });

  // ===== Fade-in on scroll =====
  const fadeEls = document.querySelectorAll(".fade-in");
  if ("IntersectionObserver" in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("visible");
          observer.unobserve(entry.target);
        }
      });
    }, { threshold: 0.12 });
    fadeEls.forEach((el) => observer.observe(el));
  } else {
    fadeEls.forEach((el) => el.classList.add("visible"));
  }

  // ===== Active nav link =====
  const navLinks = [...navMenu.querySelectorAll("a")];
  const sections = navLinks.map((a) => document.querySelector(a.getAttribute("href")));
  const sectionObserver = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        navLinks.forEach((a) => a.classList.toggle("active", a.getAttribute("href") === `#${entry.target.id}`));
      }
    });
  }, { rootMargin: "-45% 0px -50% 0px" });
  sections.forEach((s) => s && sectionObserver.observe(s));

  // ===== Footer year =====
  document.getElementById("year").textContent = new Date().getFullYear();
})();
