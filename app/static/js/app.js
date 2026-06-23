let audioContext;
let musicGain;
let musicTimer;
let musicStarted = false;
let musicStep = 0;

const defaultMusicSettings = { muted: false, volume: 0.18 };
const musicStorageKey = "fastockflow.backgroundMusic";
const musicPattern = [
  { frequencies: [261.63, 329.63], duration: 0.38 },
  { frequencies: [392.0], duration: 0.28 },
  { frequencies: [293.66, 369.99], duration: 0.38 },
  { frequencies: [440.0], duration: 0.28 },
  { frequencies: [329.63, 493.88], duration: 0.42 },
  { frequencies: [392.0], duration: 0.28 },
  { frequencies: [246.94, 329.63], duration: 0.42 },
  { frequencies: [349.23], duration: 0.32 },
];
let musicSettings = loadMusicSettings();

async function getAudioContext() {
  const AudioCtx = window.AudioContext || window.webkitAudioContext;
  if (!AudioCtx) return null;
  audioContext = audioContext || new AudioCtx();
  if (audioContext.state === "suspended") await audioContext.resume();
  return audioContext;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function loadMusicSettings() {
  try {
    const stored = JSON.parse(window.localStorage.getItem(musicStorageKey) || "{}");
    return {
      muted: Boolean(stored.muted),
      volume: clamp(Number.isFinite(Number(stored.volume)) ? Number(stored.volume) : defaultMusicSettings.volume, 0, 1),
    };
  } catch (error) {
    return { ...defaultMusicSettings };
  }
}

function saveMusicSettings() {
  try {
    window.localStorage.setItem(musicStorageKey, JSON.stringify(musicSettings));
  } catch (error) {
    // Local storage can be unavailable in private contexts; audio should still work for this page load.
  }
}

function getMusicControls() {
  return {
    toggle: document.querySelector("[data-music-toggle]"),
    volume: document.querySelector("[data-music-volume]"),
  };
}

function updateMusicControls() {
  const controls = getMusicControls();
  if (!controls.toggle || !controls.volume) return;
  const isMuted = musicSettings.muted || musicSettings.volume === 0;
  controls.toggle.setAttribute("aria-pressed", String(isMuted));
  controls.toggle.setAttribute("aria-label", isMuted ? "Play background music" : "Mute background music");
  controls.toggle.setAttribute("title", isMuted ? "Play background music" : "Mute background music");
  controls.volume.value = String(Math.round(musicSettings.volume * 100));
}

function showPageLoading() {
  document.body.classList.add("is-loading");
}

function hidePageLoading() {
  document.body.classList.remove("is-loading");
}

function setButtonLoading(button, loading) {
  if (!button) return;
  button.classList.toggle("is-loading", loading);
  button.toggleAttribute("aria-busy", loading);
  if (loading) {
    if (!Object.prototype.hasOwnProperty.call(button.dataset, "originalDisabled")) {
      button.dataset.originalDisabled = String(button.disabled);
    }
    button.disabled = true;
  } else {
    button.disabled = button.dataset.originalDisabled === "true";
    delete button.dataset.originalDisabled;
  }
}

function setFormSubmitting(form, submitter) {
  if (!form || form.classList.contains("is-submitting")) return;
  form.classList.add("is-submitting");
  form.querySelectorAll('button[type="submit"]').forEach((button) => setButtonLoading(button, true));
  if (submitter && submitter.matches("button")) setButtonLoading(submitter, true);
  showPageLoading();
}

function targetMusicVolume() {
  return musicSettings.muted ? 0 : musicSettings.volume;
}

function applyMusicGain() {
  if (!audioContext || !musicGain) return;
  const now = audioContext.currentTime;
  musicGain.gain.cancelScheduledValues(now);
  musicGain.gain.setTargetAtTime(targetMusicVolume(), now, 0.05);
}

async function ensureMusicOutput() {
  const context = await getAudioContext();
  if (!context) return null;
  if (!musicGain) {
    musicGain = context.createGain();
    musicGain.gain.value = 0;
    musicGain.connect(context.destination);
  }
  applyMusicGain();
  return context;
}

function playMusicPulse() {
  if (!audioContext || !musicGain) return;
  const note = musicPattern[musicStep % musicPattern.length];
  const now = audioContext.currentTime;
  const noteGain = audioContext.createGain();
  const filter = audioContext.createBiquadFilter();

  filter.type = "lowpass";
  filter.frequency.setValueAtTime(1500, now);
  noteGain.gain.setValueAtTime(0.0001, now);
  noteGain.gain.exponentialRampToValueAtTime(0.16, now + 0.035);
  noteGain.gain.exponentialRampToValueAtTime(0.0001, now + note.duration);
  filter.connect(noteGain);
  noteGain.connect(musicGain);

  note.frequencies.forEach((frequency, index) => {
    const oscillator = audioContext.createOscillator();
    oscillator.type = index === 0 ? "triangle" : "sine";
    oscillator.frequency.setValueAtTime(frequency, now);
    oscillator.detune.setValueAtTime(index * 4, now);
    oscillator.connect(filter);
    oscillator.start(now);
    oscillator.stop(now + note.duration + 0.04);
  });
}

function scheduleMusicPulse() {
  if (!musicStarted) return;
  if (musicSettings.muted || musicSettings.volume === 0 || document.hidden) {
    stopBackgroundMusic();
    return;
  }
  playMusicPulse();
  musicStep = (musicStep + 1) % musicPattern.length;
  musicTimer = window.setTimeout(scheduleMusicPulse, 520);
}

async function startBackgroundMusic() {
  if (musicStarted || musicSettings.muted || musicSettings.volume === 0) {
    applyMusicGain();
    return;
  }
  const context = await ensureMusicOutput();
  if (!context || document.hidden) return;
  musicStarted = true;
  scheduleMusicPulse();
}

function stopBackgroundMusic() {
  if (musicTimer) {
    window.clearTimeout(musicTimer);
    musicTimer = null;
  }
  musicStarted = false;
  applyMusicGain();
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
  const musicToggle = event.target.closest("[data-music-toggle]");
  if (musicToggle) {
    musicSettings.muted = !(musicSettings.muted || musicSettings.volume === 0);
    if (!musicSettings.muted && musicSettings.volume === 0) {
      musicSettings.volume = defaultMusicSettings.volume;
    }
    saveMusicSettings();
    updateMusicControls();
    if (musicSettings.muted) {
      stopBackgroundMusic();
    } else {
      await startBackgroundMusic();
    }
    return;
  }

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
      clone.querySelectorAll("output").forEach((output) => (output.textContent = "₹0.00"));
      clone.querySelectorAll("[data-item-picker]").forEach((picker) => delete picker.dataset.itemPickerReady);
      clone.classList.add("row-enter");
      grid.appendChild(clone);
      initializeItemPickers(clone);
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
    setButtonLoading(auto, true);
    showPageLoading();
    try {
      const response = await fetch(`/transactions/reference/${auto.dataset.autoRef}`);
      if (!response.ok) throw new Error("Reference request failed");
      const data = await response.json();
      target.value = data.reference;
    } finally {
      setButtonLoading(auto, false);
      hidePageLoading();
    }
  }

  const liveFind = event.target.closest("[data-live-find]");
  if (liveFind) {
    const form = liveFind.closest("[data-live-search-form]");
    const input = form && form.querySelector("[data-live-search]");
    applyLiveSearch(input);
  }

  const itemOpen = event.target.closest("[data-item-open]");
  if (itemOpen) {
    const picker = itemOpen.closest("[data-item-picker]");
    const input = picker && picker.querySelector("[data-item-search]");
    if (input) {
      input.focus();
      if (typeof input.showPicker === "function") input.showPicker();
    }
  }

  startBackgroundMusic();
});

document.addEventListener("submit", (event) => {
  const form = event.target;
  if (!validateItemPickers(form)) {
    event.preventDefault();
    return;
  }
  const message = form.dataset.confirm;
  if (message && !window.confirm(message)) {
    event.preventDefault();
    return;
  }
  setFormSubmitting(form, event.submitter);
  if (message && /(delete|deactivate|reverse)/i.test(message)) {
    event.preventDefault();
    playTone("delete");
    window.setTimeout(() => HTMLFormElement.prototype.submit.call(form), 130);
  }
});

window.addEventListener("pageshow", () => {
  hidePageLoading();
  document.querySelectorAll("form.is-submitting").forEach((form) => {
    form.classList.remove("is-submitting");
    form.querySelectorAll("button.is-loading").forEach((button) => setButtonLoading(button, false));
  });
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

function itemOptionLabel(option) {
  return (option?.value || "").trim();
}

function initializeItemPickers(root = document) {
  root.querySelectorAll("[data-item-picker]").forEach((picker) => {
    if (picker.dataset.itemPickerReady === "true") return;
    const input = picker.querySelector("[data-item-search]");
    const datalist = picker.querySelector("[data-item-options]");
    if (!input || !datalist) return;
    const id = `item_options_${Date.now()}_${Math.random().toString(36).slice(2)}`;
    datalist.id = id;
    input.setAttribute("list", id);
    picker.dataset.itemPickerReady = "true";
    syncItemValue(input);
  });
}

function matchingItemOption(input) {
  const picker = input.closest("[data-item-picker]");
  const datalist = picker && picker.querySelector("[data-item-options]");
  if (!datalist) return null;
  const value = input.value.trim().toLowerCase();
  if (!value) return null;
  return Array.from(datalist.options).find((option) => itemOptionLabel(option).toLowerCase() === value) || null;
}

function syncItemValue(input) {
  const picker = input.closest("[data-item-picker]");
  const hidden = picker && picker.querySelector("[data-item-value]");
  if (!hidden) return false;
  const option = matchingItemOption(input);
  hidden.value = option ? option.dataset.itemId || "" : "";
  input.setCustomValidity(input.value.trim() && !hidden.value ? "Select an item from the list." : "");
  return Boolean(hidden.value);
}

function validateItemPickers(form) {
  const inputs = Array.from(form.querySelectorAll("[data-item-search]"));
  for (const input of inputs) {
    if (!syncItemValue(input)) {
      input.reportValidity();
      return false;
    }
  }
  return true;
}

function applyLiveSearch(input) {
  if (!input || !input.dataset.liveTarget) return;
  const target = document.querySelector(input.dataset.liveTarget);
  if (!target) return;
  const query = input.value.trim().toLowerCase();
  const tables = target.matches("table") ? [target] : Array.from(target.querySelectorAll("table"));

  tables.forEach((table) => {
    const rows = Array.from(table.querySelectorAll("tbody tr"));
    const emptyRows = rows.filter((row) => row.matches("[data-live-empty], .empty"));
    let visibleCount = 0;

    rows.forEach((row) => {
      if (row.matches("[data-live-empty]")) return;
      if (row.classList.contains("empty")) {
        row.hidden = Boolean(query);
        return;
      }
      const visible = !query || row.textContent.toLowerCase().includes(query);
      row.hidden = !visible;
      if (visible) visibleCount += 1;
    });

    emptyRows
      .filter((row) => row.matches("[data-live-empty]"))
      .forEach((row) => {
        row.hidden = !query || visibleCount > 0;
      });
  });
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
  if (event.target.matches("[data-music-volume]")) {
    musicSettings.volume = clamp(parseInt(event.target.value, 10) / 100 || 0, 0, 1);
    musicSettings.muted = musicSettings.volume === 0;
    saveMusicSettings();
    updateMusicControls();
    applyMusicGain();
    startBackgroundMusic();
    return;
  }

  if (
    event.target.matches('input[name="quantity[]"]') ||
    event.target.matches('input[name="rate[]"]') ||
    event.target.matches('input[name="gst_percent[]"]')
  ) {
    updateLineTotal(event.target.closest(".line-row"));
  }

  if (event.target.matches("[data-item-search]")) {
    syncItemValue(event.target);
  }

  if (event.target.matches("[data-live-search]")) {
    applyLiveSearch(event.target);
  }
});

document.addEventListener("visibilitychange", () => {
  if (document.hidden) {
    stopBackgroundMusic();
  } else {
    startBackgroundMusic();
  }
});

updateMusicControls();
document.querySelectorAll("form").forEach(filterStockBooks);
document.querySelectorAll(".line-row").forEach(updateLineTotal);
initializeItemPickers();
document.querySelectorAll("[data-live-search]").forEach(applyLiveSearch);
