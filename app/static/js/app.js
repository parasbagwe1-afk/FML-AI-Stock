let audioContext;

async function getAudioContext() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;
  audioContext = audioContext || new AudioCtx();
  if (audioContext.state === "suspended") await audioContext.resume();
  return audioContext;
}

async function playTone(kind) {
  const context = await getAudioContext();
  if (!context) return;
  const now = context.currentTime;
  const gain = context.createGain();
  const oscillator = context.createOscillator();
  const settings = {
    add: { start: 640, end: 980, duration: 0.11, volume: 0.09 },
    remove: { start: 460, end: 260, duration: 0.12, volume: 0.075 },
    delete: { start: 260, end: 150, duration: 0.16, volume: 0.09 },
  }[kind] || { start: 520, end: 520, duration: 0.09, volume: 0.07 };

  oscillator.type = "sine";
  oscillator.frequency.setValueAtTime(settings.start, now);
  oscillator.frequency.exponentialRampToValueAtTime(settings.end, now + settings.duration);
  gain.gain.setValueAtTime(0.0001, now);
  gain.gain.exponentialRampToValueAtTime(settings.volume, now + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, now + settings.duration);
  oscillator.connect(gain);
  gain.connect(context.destination);
  oscillator.start(now);
  oscillator.stop(now + settings.duration + 0.015);
}

document.addEventListener("click", async (event) => {
  const toggle = event.target.closest("[data-toggle-password]");
  if (toggle) {
    const input = document.querySelector(toggle.dataset.togglePassword);
    if (input) {
      input.type = input.type === "password" ? "text" : "password";
      toggle.textContent = input.type === "password" ? "Show" : "Hide";
    }
  }

  const add = event.target.closest("[data-add-line]");
  if (add) {
    const grid = add.previousElementSibling;
    const row = grid && grid.querySelector(".line-row");
    if (grid && row) {
      const clone = row.cloneNode(true);
      clone.querySelectorAll("input").forEach((input) => (input.value = ""));
      clone.querySelectorAll("select").forEach((select) => (select.selectedIndex = 0));
      clone.querySelectorAll("output").forEach((output) => (output.textContent = "₹0.00"));
      clone.classList.add("row-enter");
      grid.appendChild(clone);
      updateLineTotal(clone);
      playTone("add");
      window.setTimeout(() => clone.classList.remove("row-enter"), 220);
    }
  }

  const remove = event.target.closest("[data-remove-line]");
  if (remove) {
    const grid = remove.closest("[data-line-grid]");
    const rows = grid.querySelectorAll(".line-row");
    if (rows.length > 1) {
      const row = remove.closest(".line-row");
      row.classList.add("row-exit");
      playTone("remove");
      window.setTimeout(() => row.remove(), 150);
    }
  }

  const auto = event.target.closest("[data-auto-ref]");
  if (auto) {
    const target = document.querySelector(auto.dataset.target);
    if (!target) return;
    auto.disabled = true;
    try {
      const response = await fetch(`/transactions/reference/${auto.dataset.autoRef}`);
      const data = await response.json();
      target.value = data.reference;
    } finally {
      auto.disabled = false;
    }
  }
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  const message = form.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
    return;
  }
  if (message && /(delete|deactivate|reverse)/i.test(message)) {
    event.preventDefault();
    playTone("delete");
    window.setTimeout(() => HTMLFormElement.prototype.submit.call(form), 130);
  }
});

function formatPreviewMoney(value) {
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(Number.isFinite(value) ? value : 0);
}

function updateLineTotal(row) {
  if (!row) return;
  const quantity = parseFloat(row.querySelector('input[name="quantity[]"]')?.value || "0");
  const rate = parseFloat(row.querySelector('input[name="rate[]"]')?.value || "0");
  const gst = parseFloat(row.querySelector('input[name="gst_percent[]"]')?.value || "0");
  const output = row.querySelector(".line-total-preview");
  if (!output) return;
  const subtotal = quantity * rate;
  output.textContent = formatPreviewMoney(subtotal + subtotal * gst / 100);
}

function filterStockBookPair(form, companySelector, stockBookSelector, categorySelector) {
  const company = form.querySelector(companySelector);
  const stockBook = form.querySelector(stockBookSelector);
  const category = categorySelector ? form.querySelector(categorySelector) : null;
  if (!company || !stockBook) return;

  const companyId = company.value;
  const bookType = category ? category.value : "";
  let selectedStillVisible = false;

  stockBook.querySelectorAll("option").forEach((option) => {
    const visible =
      !option.dataset.companyId ||
      (option.dataset.companyId === companyId && (!bookType || option.dataset.bookType === bookType));
    option.hidden = !visible;
    option.disabled = !visible;
    if (visible && option.selected) selectedStillVisible = true;
  });

  if (!selectedStillVisible) {
    const firstVisible = Array.from(stockBook.options).find((option) => !option.disabled);
    if (firstVisible) firstVisible.selected = true;
  }
}

function filterStockBooks(form) {
  if (!form) return;
  const categorySelector = form.querySelector('select[name="purchase_type"]')
    ? 'select[name="purchase_type"]'
    : form.querySelector('select[name="sale_type"]')
      ? 'select[name="sale_type"]'
      : null;
  filterStockBookPair(form, 'select[name="company_id"]', 'select[name="stock_book_id"]', categorySelector);
  filterStockBookPair(form, 'select[name="from_company_id"]', 'select[name="from_stock_book_id"]');
  filterStockBookPair(form, 'select[name="to_company_id"]', 'select[name="to_stock_book_id"]');
}

document.addEventListener("change", (event) => {
  if (
    event.target.matches('select[name="company_id"]') ||
    event.target.matches('select[name="from_company_id"]') ||
    event.target.matches('select[name="to_company_id"]') ||
    event.target.matches('select[name="purchase_type"]') ||
    event.target.matches('select[name="sale_type"]')
  ) {
    filterStockBooks(event.target.closest("form"));
  }
});

document.addEventListener("input", (event) => {
  if (
    event.target.matches('input[name="quantity[]"]') ||
    event.target.matches('input[name="rate[]"]') ||
    event.target.matches('input[name="gst_percent[]"]')
  ) {
    updateLineTotal(event.target.closest(".line-row"));
  }
});

document.querySelectorAll("form").forEach(filterStockBooks);
document.querySelectorAll(".line-row").forEach(updateLineTotal);
