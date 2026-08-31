(function () {
  const root = document.documentElement;
  const saved = localStorage.getItem("dukaan-theme") || "light";
  root.setAttribute("data-theme", saved);

  function updateIcon() {
    const btn = document.getElementById("theme-toggle-btn");
    if (btn) {
      btn.textContent = root.getAttribute("data-theme") === "dark" ? "☀️" : "🌙";
    }
  }

  document.addEventListener("DOMContentLoaded", function () {
    updateIcon();
    const btn = document.getElementById("theme-toggle-btn");
    if (btn) {
      btn.addEventListener("click", function () {
        const current = root.getAttribute("data-theme");
        const next = current === "dark" ? "light" : "dark";
        root.setAttribute("data-theme", next);
        localStorage.setItem("dukaan-theme", next);
        updateIcon();
      });
    }
  });
})();
