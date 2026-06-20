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
      grid.appendChild(clone);
    }
  }

  const remove = event.target.closest("[data-remove-line]");
  if (remove) {
    const grid = remove.closest("[data-line-grid]");
    const rows = grid.querySelectorAll(".line-row");
    if (rows.length > 1) {
      remove.closest(".line-row").remove();
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
  }
});

function filterStockBooks(form) {
  const company = form.querySelector('select[name="company_id"]');
  const category =
    form.querySelector('select[name="purchase_type"]') ||
    form.querySelector('select[name="sale_type"]');
  const stockBook = form.querySelector('select[name="stock_book_id"]');
  if (!company || !category || !stockBook) return;

  const companyId = company.value;
  const bookType = category.value;
  let selectedStillVisible = false;

  stockBook.querySelectorAll("option").forEach((option) => {
    const visible =
      !option.dataset.companyId ||
      (option.dataset.companyId === companyId && option.dataset.bookType === bookType);
    option.hidden = !visible;
    option.disabled = !visible;
    if (visible && option.selected) selectedStillVisible = true;
  });

  if (!selectedStillVisible) {
    const firstVisible = Array.from(stockBook.options).find((option) => !option.disabled);
    if (firstVisible) firstVisible.selected = true;
  }
}

document.addEventListener("change", (event) => {
  if (
    event.target.matches('select[name="company_id"]') ||
    event.target.matches('select[name="purchase_type"]') ||
    event.target.matches('select[name="sale_type"]')
  ) {
    filterStockBooks(event.target.closest("form"));
  }
});

document.querySelectorAll("form").forEach(filterStockBooks);
