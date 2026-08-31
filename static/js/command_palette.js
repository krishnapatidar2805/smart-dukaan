// Global Command Palette (Ctrl + K / Cmd + K)
document.addEventListener("DOMContentLoaded", function () {
  const modal = document.getElementById("command-palette-modal");
  const input = document.getElementById("command-palette-input");
  const resultsContainer = document.getElementById("command-palette-results");
  if (!modal || !input || !resultsContainer) return;

  const commands = [
    { title: "🧾 New POS Bill", category: "Billing", url: "/billing/new/", shortcut: "N" },
    { title: "📊 Store Dashboard", category: "Navigation", url: "/", shortcut: "D" },
    { title: "📦 Inventory & Stock", category: "Products", url: "/inventory/", shortcut: "I" },
    { title: "🏷️ Barcode & Price Stickers", category: "Products", url: "/inventory/barcodes/", shortcut: "B" },
    { title: "➕ Add New Product", category: "Products", url: "/inventory/add/", shortcut: "P" },
    { title: "💰 Daily Cash Register", category: "Cashier", url: "/billing/cash-register/", shortcut: "C" },
    { title: "🏢 Purchases & Suppliers", category: "Suppliers", url: "/purchases/", shortcut: "S" },
    { title: "📥 Stock Inward (PO)", category: "Suppliers", url: "/purchases/new/", shortcut: "O" },
    { title: "💳 Udhaar (Credit) Ledger", category: "Khata", url: "/udhaar/", shortcut: "U" },
    { title: "🔄 Returns & Refunds", category: "Billing", url: "/billing/returns/", shortcut: "R" },
    { title: "📄 Bill History & Sales", category: "Billing", url: "/billing/", shortcut: "H" },
    { title: "🌐 Public Online Store", category: "Online", url: "/store/1/", shortcut: "W" },
    { title: "📲 Counter QR Standee", category: "Online", url: "/dashboard/store/1/qr/", shortcut: "Q" },
    { title: "🤖 AI Business Assistant", category: "AI Tools", url: "/assistant/", shortcut: "A" },
    { title: "👥 Staff Management", category: "Admin", url: "/accounts/staff/", shortcut: "M" },
    { title: "📜 Activity Log & Audit", category: "Admin", url: "/accounts/audit-log/", shortcut: "L" },
  ];

  let selectedIndex = 0;
  let filteredCommands = [...commands];

  function renderCommands() {
    resultsContainer.innerHTML = "";
    if (filteredCommands.length === 0) {
      resultsContainer.innerHTML = '<div style="padding:16px; text-align:center; color:var(--text-muted); font-size:0.9rem;">No matching actions or pages found.</div>';
      return;
    }

    filteredCommands.forEach((cmd, idx) => {
      const item = document.createElement("a");
      item.href = cmd.url;
      item.className = "command-item" + (idx === selectedIndex ? " active" : "");
      item.innerHTML = `
        <div style="display:flex; align-items:center; gap:10px;">
          <span style="font-size:1.1rem;">${cmd.title.split(" ")[0]}</span>
          <div>
            <div style="font-weight:600; font-size:0.92rem; color:var(--text);">${cmd.title.substring(cmd.title.indexOf(" ") + 1)}</div>
            <div style="font-size:0.75rem; color:var(--text-muted);">${cmd.category}</div>
          </div>
        </div>
        <kbd style="padding:2px 8px; font-size:0.75rem; background:var(--surface-hover); border:1px solid var(--border); border-radius:4px; color:var(--text-muted);">${cmd.shortcut}</kbd>
      `;
      item.addEventListener("click", () => closeModal());
      resultsContainer.appendChild(item);
    });
  }

  function openModal() {
    modal.style.display = "flex";
    input.value = "";
    filteredCommands = [...commands];
    selectedIndex = 0;
    renderCommands();
    setTimeout(() => input.focus(), 50);
  }

  function closeModal() {
    modal.style.display = "none";
  }

  // Global Keyboard Shortcuts
  document.addEventListener("keydown", function (e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "k") {
      e.preventDefault();
      if (modal.style.display === "flex") {
        closeModal();
      } else {
        openModal();
      }
    } else if (e.key === "Escape" && modal.style.display === "flex") {
      closeModal();
    }
  });

  input.addEventListener("input", function () {
    const val = input.value.toLowerCase().trim();
    filteredCommands = commands.filter(
      (c) => c.title.toLowerCase().includes(val) || c.category.toLowerCase().includes(val)
    );
    selectedIndex = 0;
    renderCommands();
  });

  input.addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      selectedIndex = (selectedIndex + 1) % filteredCommands.length;
      renderCommands();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      selectedIndex = (selectedIndex - 1 + filteredCommands.length) % filteredCommands.length;
      renderCommands();
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (filteredCommands[selectedIndex]) {
        window.location.href = filteredCommands[selectedIndex].url;
      }
    }
  });

  modal.addEventListener("click", function (e) {
    if (e.target === modal) {
      closeModal();
    }
  });

  // Global trigger button in topbar
  const triggerBtn = document.getElementById("btn-command-palette-trigger");
  if (triggerBtn) {
    triggerBtn.addEventListener("click", openModal);
  }
});
