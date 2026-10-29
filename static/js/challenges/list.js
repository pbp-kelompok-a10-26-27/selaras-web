// Challenge list: live search and status filter, weather widget, leave modal.
import { showMessagesAsToasts } from "../accounts/shared.js";

const favicon = document.querySelector('link[rel~="icon"]');
if (favicon && !favicon.getAttribute("href")?.startsWith("/")) {
  favicon.setAttribute("href", "/static/assets/images/logo.svg");
}

const page = document.getElementById("challengesPage");

if (page) {
  init(page);
}

const SVG_NS = "http://www.w3.org/2000/svg";
const WEATHER_ICONS = {
  sun: [
    '<circle cx="12" cy="12" r="4"/>',
    '<path d="M12 2v2M12 20v2M2 12h2M20 12h2m-15.07-7.07 1.41 1.41m11.32 11.32 1.41 1.41m0-14.14-1.41 1.41M6.34 17.66l-1.41 1.41"/>',
  ].join(""),
  rain: '<path d="M4 14.9A7 7 0 1 1 15.71 8h1.79a4.5 4.5 0 0 1 2.5 8.24M16 14v6M8 14v6M12 16v6"/>',
  cloud: '<path d="M17.5 19H9a7 7 0 1 1 6.71-9h1.79a4.5 4.5 0 1 1 0 9Z"/>',
};

function init(root) {
  const { listUrl, weatherUrl, leaveUrlTemplate } = root.dataset;
  const searchInput = document.getElementById("challengesSearch");
  const statusInput = document.getElementById("challengesStatus");
  const grid = document.getElementById("challengesGrid");
  const countEl = document.getElementById("challengesResultCount");
  const chipsEl = document.getElementById("challengesActiveFilters");
  const skeleton = document.getElementById("tpl-challenges-skeleton");

  const state = {
    search: searchInput ? searchInput.value.trim() : "",
    status: root.dataset.status || "all",
  };
  let debounceTimer = null;
  let controller = null;

  showMessagesAsToasts();

  // ---------------------------------------------------------------- filters

  const statusLabel = (value) =>
    statusInput
      ?.closest(".custom-dropdown")
      ?.querySelector(`.dropdown-item[data-value="${CSS.escape(value)}"]`)
      ?.dataset.label ?? value;

  function syncDropdown(value) {
    if (!statusInput) return;
    statusInput.value = value;
    const label = statusInput
      .closest(".custom-dropdown")
      ?.querySelector(".dropdown-label");
    if (label) {
      label.textContent = statusLabel(value);
      label.classList.remove("text-foreground/80");
    }
  }

  function createFilterChip(label, removeLabel, onRemove) {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className =
      "group/chip inline-flex min-h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-full border border-neutral-500 bg-neutral-50 py-1 pl-3 pr-1.5 font-sans text-sm font-semibold text-foreground outline-none transition-all duration-200 hover:shadow-sm focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 active:scale-[0.97]";
    chip.title = removeLabel;
    chip.setAttribute("aria-label", removeLabel);

    const text = document.createElement("span");
    text.textContent = label;

    const close = document.createElement("span");
    close.className =
      "flex h-6 w-6 items-center justify-center rounded-full text-neutral-800 transition-colors duration-200 group-hover/chip:bg-neutral-900/10 group-hover/chip:text-foreground";
    close.setAttribute("aria-hidden", "true");
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("class", "w-4 h-4");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");
    svg.innerHTML = '<path d="M18 6 6 18M6 6l12 12"/>';
    close.append(svg);

    chip.append(text, close);
    chip.addEventListener("click", onRemove);
    return chip;
  }

  function renderChips() {
    if (!chipsEl) return;
    chipsEl.replaceChildren();
    if (state.search) {
      chipsEl.append(
        createFilterChip(
          `\u201c${state.search}\u201d`,
          "Hapus pencarian",
          () => {
            if (searchInput) searchInput.value = "";
            apply({ search: "" });
          },
        ),
      );
    }
    if (state.status !== "all") {
      chipsEl.append(
        createFilterChip(statusLabel(state.status), "Hapus filter status", () =>
          apply({ status: "all" }),
        ),
      );
    }
  }

  function renderCount(count) {
    if (countEl) {
      countEl.textContent = `${count} challenge`;
    }
  }

  async function load({ pushHistory = true } = {}) {
    if (!grid) return;
    controller?.abort();
    controller = new AbortController();

    grid.setAttribute("aria-busy", "true");
    if (skeleton) grid.innerHTML = skeleton.innerHTML;

    const params = new URLSearchParams();
    if (state.search) params.set("search", state.search);
    if (state.status !== "all") params.set("status", state.status);

    try {
      const query = new URLSearchParams(params);
      query.set("ajax", "1");
      const response = await fetch(`${listUrl}?${query}`, {
        headers: { "X-Requested-With": "XMLHttpRequest" },
        signal: controller.signal,
      });
      if (!response.ok) throw new Error("Request failed");
      const data = await response.json();

      grid.innerHTML = data.html;
      grid.setAttribute("aria-busy", "false");
      renderCount(data.count);
      renderChips();
      bindGridActions();

      if (pushHistory) {
        const url = new URL(window.location);
        url.search = params.toString();
        window.history.pushState({}, "", url);
      }
    } catch (error) {
      if (error.name === "AbortError") return;
      grid.setAttribute("aria-busy", "false");
      grid.innerHTML = errorState();
      grid
        .querySelector("[data-retry]")
        ?.addEventListener("click", () => load({ pushHistory: false }));
    }
  }

  function errorState() {
    return `
      <div class="mx-auto my-8 max-w-xl rounded-2xl border border-neutral-400 bg-neutral-50 p-12 text-center" role="alert">
        <h2 class="font-display text-h5 text-foreground">Could not load challenges</h2>
        <p class="mx-auto mt-1 mb-6 max-w-md font-sans text-sm text-neutral-900">Check your connection and try again.</p>
        <button type="button" data-retry class="inline-flex min-h-10 items-center justify-center rounded-xl border border-neutral-400 bg-neutral-50 px-4 font-sans text-sm font-semibold text-secondary-800 outline-none transition-colors hover:bg-neutral-300 focus-visible:ring-2 focus-visible:ring-primary-500">Retry</button>
      </div>`;
  }

  function apply(changes) {
    Object.assign(state, changes);
    if ("status" in changes) syncDropdown(state.status);
    load();
  }

  searchInput?.addEventListener("input", () => {
    clearTimeout(debounceTimer);
    debounceTimer = setTimeout(
      () => apply({ search: searchInput.value.trim() }),
      280,
    );
  });

  // The form also works without JS; with JS the dropdown and search update live
  document
    .getElementById("challengesFilterForm")
    ?.addEventListener("submit", (event) => event.preventDefault());

  statusInput?.addEventListener("change", () => {
    const value = statusInput.value || "all";
    if (value !== state.status) apply({ status: value });
  });

  window.addEventListener("popstate", () => {
    const params = new URL(window.location).searchParams;
    state.search = params.get("search") || "";
    state.status = params.get("status") || "all";
    if (searchInput) searchInput.value = state.search;
    syncDropdown(state.status);
    load({ pushHistory: false });
  });

  // ------------------------------------------------- cards and leave modal

  function bindGridActions() {
    grid.querySelectorAll(".challenge-card").forEach((card) => {
      card.addEventListener("click", (event) => {
        if (event.target.closest("a, button, form, [data-modal-open]")) return;
        const url = card.dataset.cardUrl;
        if (url) window.location.href = url;
      });
    });

    grid
      .querySelector("#btn-reset-filters")
      ?.addEventListener("click", () => {
        if (searchInput) searchInput.value = "";
        apply({ search: "", status: "all" });
      });

    grid.querySelectorAll("[data-trigger-leave]").forEach((trigger) => {
      trigger.addEventListener("click", () => {
        const card = trigger.closest("[data-slug]");
        const form = document.getElementById("leave-modal-form");
        const title = document.getElementById("leave-modal-challenge-title");
        if (form && card) {
          form.action = leaveUrlTemplate.replace(
            "slug-placeholder",
            card.dataset.slug,
          );
        }
        if (title && card) title.textContent = `\u201c${card.dataset.title}\u201d`;
      });
    });
  }

  renderChips();
  bindGridActions();

  // ---------------------------------------------------------------- weather

  const detectButton = document.getElementById("btn-detect-location");
  const statusMessage = document.getElementById("weather-location-status");

  function setWeatherStatus(message, isError = false) {
    if (!statusMessage) return;
    statusMessage.classList.remove("hidden", "text-red-100", "text-secondary-800");
    statusMessage.classList.add(isError ? "text-red-100" : "text-secondary-800");
    statusMessage.textContent = message;
  }

  function weatherIcon(name) {
    const key =
      name === "sun" || name === "cloud-sun"
        ? "sun"
        : name === "cloud-rain"
          ? "rain"
          : "cloud";
    return `<svg class="w-6 h-6" xmlns="${SVG_NS}" width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${WEATHER_ICONS[key]}</svg>`;
  }

  function updateWeather(data) {
    const set = (id, value) => {
      const node = document.getElementById(id);
      if (node) node.textContent = value;
    };
    set("weather-temp-val", `${data.temperature}\u00b0C`);
    set("weather-cond-text", data.condition);
    set("weather-suggestion", data.suggestion);
    set("weather-location-label", data.location_label || "Lokasimu");
    const slot = document.getElementById("weather-icon-slot");
    if (slot) slot.innerHTML = weatherIcon(data.icon);
  }

  async function syncWeather(lat, lon) {
    setWeatherStatus("Mengambil prakiraan cuaca di lokasimu\u2026");
    try {
      const response = await fetch(
        `${weatherUrl}?lat=${encodeURIComponent(lat)}&lon=${encodeURIComponent(lon)}`,
      );
      if (!response.ok) throw new Error("Request failed");
      updateWeather(await response.json());
      setWeatherStatus("Cuaca sudah disesuaikan dengan lokasimu.");
      localStorage.setItem("selaras_weather_lat", lat);
      localStorage.setItem("selaras_weather_lon", lon);
      setTimeout(() => statusMessage?.classList.add("hidden"), 4000);
    } catch {
      setWeatherStatus(
        "Cuaca belum bisa diperbarui. Kami tampilkan prakiraan bawaan.",
        true,
      );
    }
  }

  detectButton?.addEventListener("click", () => {
    if (!navigator.geolocation) {
      setWeatherStatus("Browser kamu belum mendukung akses lokasi.", true);
      return;
    }
    setWeatherStatus("Mencari lokasimu\u2026");
    detectButton.setAttribute("disabled", "true");
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        detectButton.removeAttribute("disabled");
        syncWeather(coords.latitude, coords.longitude);
      },
      (error) => {
        detectButton.removeAttribute("disabled");
        let message = "Lokasimu belum bisa diakses.";
        if (error.code === error.PERMISSION_DENIED) {
          message = "Izin lokasi ditolak.";
        } else if (error.code === error.TIMEOUT) {
          message = "Permintaan lokasi kelamaan. Coba lagi, ya.";
        }
        setWeatherStatus(`${message} Kami tampilkan prakiraan bawaan.`, true);
      },
      { timeout: 8000, maximumAge: 300000 },
    );
  });

  // Re-use a location the user already allowed in this browser
  const cachedLat = localStorage.getItem("selaras_weather_lat");
  const cachedLon = localStorage.getItem("selaras_weather_lon");
  if (cachedLat && cachedLon && root.dataset.weatherCustom !== "true") {
    syncWeather(cachedLat, cachedLon);
  }
}
