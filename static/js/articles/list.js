// Article list: live search, and category / topic / status / page links that update the
// results in place. Every link and the search form also work as normal page loads.
import { revealOnScroll, showMessagesAsToasts } from "../accounts/shared.js";

const page = document.getElementById("articlesPage");

if (page) {
  init(page);
}

function init(root) {
  const listUrl = root.dataset.listUrl;
  const form = document.getElementById("articlesSearchForm");
  const searchInput = document.getElementById("article-search");
  const results = document.getElementById("articlesResults");
  const regions = ["articlesResults", "articlesFilters", "articlesSearchHidden"];
  const skeleton = document.getElementById("tpl-articles-skeleton");
  let controller = null;
  let debounceTimer = null;

  showMessagesAsToasts();
  revealOnScroll();
  setUpTagToggle();

  // Long topic lists start folded; the toggle shows the rest
  function setUpTagToggle() {
    const toggle = document.querySelector("[data-tag-toggle]");
    const extras = document.querySelectorAll("[data-tag-extra]");
    if (!toggle || !extras.length) return;

    const label = toggle.querySelector("[data-tag-toggle-label]");
    const setOpen = (open) => {
      extras.forEach((tag) => (tag.hidden = !open));
      toggle.setAttribute("aria-expanded", String(open));
      label.textContent = open ? "Lebih sedikit" : `Lihat semua topik (+${extras.length})`;
      toggle.querySelector("svg")?.classList.toggle("rotate-180", open);
    };
    toggle.hidden = false;
    setOpen(false);
    toggle.addEventListener("click", () =>
      setOpen(toggle.getAttribute("aria-expanded") !== "true"),
    );
  }

  async function load(url, { scroll = false, push = false } = {}) {
    controller?.abort();
    controller = new AbortController();

    results.setAttribute("aria-busy", "true");
    if (skeleton) results.replaceChildren(skeleton.content.cloneNode(true));

    try {
      const response = await fetch(url, {
        signal: controller.signal,
        headers: { "X-Requested-With": "fetch" },
        credentials: "same-origin",
      });
      // 400 still renders the page, with the "filter could not be applied" notice
      if (!response.ok && response.status !== 400) throw new Error(String(response.status));

      const doc = new DOMParser().parseFromString(await response.text(), "text/html");
      regions.forEach((id) => {
        const fresh = doc.getElementById(id);
        if (fresh) document.getElementById(id).innerHTML = fresh.innerHTML;
      });
      window.history[push ? "pushState" : "replaceState"](null, "", url);
      setUpTagToggle();
      revealOnScroll();
      if (scroll) results.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      if (error.name !== "AbortError") window.location.assign(url);
    } finally {
      results.removeAttribute("aria-busy");
    }
  }

  function searchUrl() {
    const params = new URLSearchParams(window.location.search);
    const value = searchInput.value.trim();
    if (value) params.set("search", value);
    else params.delete("search");
    params.delete("page");
    return params.size ? `${listUrl}?${params}` : listUrl;
  }

  searchInput.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(() => load(searchUrl()), 350);
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    clearTimeout(debounceTimer);
    load(searchUrl());
  });

  document.addEventListener("click", (event) => {
    const link = event.target.closest("a[data-articles-link], [data-pagination] a[href]");
    if (!link || event.metaKey || event.ctrlKey || event.shiftKey || event.button !== 0) return;

    const url = new URL(link.getAttribute("href"), window.location.href);
    if (url.pathname !== new URL(listUrl, window.location.href).pathname) return;

    event.preventDefault();
    if (link.hasAttribute("data-articles-reset")) searchInput.value = "";
    else searchInput.value = url.searchParams.get("search") ?? "";
    load(`${url.pathname}${url.search}`, {
      scroll: Boolean(link.closest("[data-pagination]")),
      push: true,
    });
  });

  window.addEventListener("popstate", () => {
    searchInput.value = new URLSearchParams(window.location.search).get("search") ?? "";
    load(window.location.pathname + window.location.search);
  });
}
