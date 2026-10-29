// Campaign list: live search and status filter. The grid is fetched from the same URL a
// plain form submit would use and swapped in place, so the page also works without this script.
import { revealOnScroll, showMessagesAsToasts } from "../accounts/shared.js";

const page = document.getElementById("donationsPage");

if (page) {
  init(page);
}

function init(root) {
  const { listUrl } = root.dataset;
  const form = document.getElementById("donationsFilterForm");
  const searchInput = document.getElementById("donationsSearch");
  const statusInput = document.getElementById("donationsStatus");
  const grid = document.getElementById("donationsGrid");
  const count = document.getElementById("donationsResultCount");
  const skeleton = document.getElementById("tpl-donations-skeleton");
  const statusButtons = [...root.querySelectorAll("[data-status-filter]")];

  const state = {
    search: searchInput.value.trim(),
    status: statusInput.value,
  };
  let debounceTimer = null;
  let controller = null;

  showMessagesAsToasts();
  revealOnScroll();

  function markSelectedStatus() {
    statusButtons.forEach((button) => {
      const selected = button.dataset.statusFilter === state.status;
      button.classList.toggle("ring-2", selected);
      button.classList.toggle("ring-primary-300", selected);
      button.classList.toggle("ring-offset-2", selected);
      if (selected) {
        button.setAttribute("aria-current", "page");
      } else {
        button.removeAttribute("aria-current");
      }
      // Keep the plain links in step with the search box
      const params = new URLSearchParams();
      if (state.search) params.set("search", state.search);
      if (button.dataset.statusFilter) params.set("status", button.dataset.statusFilter);
      button.setAttribute("href", params.size ? `?${params}` : "?");
    });
  }

  function buildUrl() {
    const params = new URLSearchParams();
    if (state.search) params.set("search", state.search);
    if (state.status) params.set("status", state.status);
    return params.size ? `${listUrl}?${params}` : listUrl;
  }

  async function load() {
    const url = buildUrl();
    statusInput.value = state.status;
    markSelectedStatus();
    window.history.replaceState(null, "", url);

    controller?.abort();
    controller = new AbortController();

    grid.setAttribute("aria-busy", "true");
    if (skeleton) grid.replaceChildren(skeleton.content.cloneNode(true));

    try {
      const response = await fetch(url, {
        signal: controller.signal,
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin",
      });
      if (!response.ok) throw new Error(String(response.status));

      const doc = new DOMParser().parseFromString(await response.text(), "text/html");
      const freshGrid = doc.getElementById("donationsGrid");
      if (!freshGrid) throw new Error("grid missing");

      grid.innerHTML = freshGrid.innerHTML;
      count.textContent = doc.getElementById("donationsResultCount").textContent.trim();
      revealOnScroll();
    } catch (error) {
      if (error.name === "AbortError") return;
      // Anything unexpected: let the browser do a normal page load
      window.location.assign(url);
      return;
    } finally {
      grid.removeAttribute("aria-busy");
    }
  }

  searchInput.addEventListener("input", () => {
    state.search = searchInput.value.trim();
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(load, 300);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    clearTimeout(debounceTimer);
    state.search = searchInput.value.trim();
    load();
  });

  statusButtons.forEach((button) =>
    button.addEventListener("click", (event) => {
      event.preventDefault();
      state.status = button.dataset.statusFilter;
      load();
    }),
  );

  grid.addEventListener("click", (event) => {
    if (!event.target.closest("#btn-reset-filters")) return;
    state.search = "";
    state.status = "";
    searchInput.value = "";
    clearTimeout(debounceTimer);
    load();
    searchInput.focus();
  });
}
