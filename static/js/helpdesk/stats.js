import "./../components/toast/toast.js";
import {
  TICKET_PRIORITY_CONFIG,
  TICKET_STATUS_CONFIG,
  cloneTemplate,
  cloneTemplateContent,
  createChipElement,
  createIcon,
  createTicketIdElement,
  createPersonElement,
  createPagination,
  createTimeElement,
  el,
  formatPageRange,
  renderLucideIcons,
} from "./shared.js";

const ticketStatsContainer = document.getElementById("ticketStats");
const STATS_API_URL = ticketStatsContainer?.dataset.statsUrl;

const ticketsContainer = document.getElementById("ticketsContainer");
const TICKETS_API_URL = ticketsContainer?.dataset.ticketsUrl;

const prefersReducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)",
);

// Shared fetch helper for the helpdesk JSON endpoints
async function fetchJson(url, resourceName, { signal } = {}) {
  const response = await fetch(url, {
    headers: { Accept: "application/json" },
    signal,
  });

  if (!response.ok)
    throw new Error(`Gagal memuat ${resourceName} (${response.status})`);

  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json"))
    throw new Error("Server tidak merespons dengan benar. Sesimu mungkin sudah habis.");

  return response.json();
}

async function fetchTicketStats() {
  const data = await fetchJson(STATS_API_URL, "statistik tiket");
  return data.stats ?? [];
}

async function fetchTickets(params, signal) {
  const queryString = params.toString();
  const url = queryString ? `${TICKETS_API_URL}?${queryString}` : TICKETS_API_URL;
  const data = await fetchJson(url, "tickets", { signal });
  const tickets = data.tickets ?? [];
  return { tickets, totalCount: data.total_count ?? tickets.length, pagination: data.pagination };
}

function createTicketsCardElement(ticket, index = 0) {
  const statusConfig =
    TICKET_STATUS_CONFIG[ticket.status] ?? TICKET_STATUS_CONFIG.open;
  const priorityConfig =
    TICKET_PRIORITY_CONFIG[ticket.priority] ?? TICKET_PRIORITY_CONFIG.normal;
  const titleId = `ticket-title-${ticket.id}`;

  const ticketDiv = el(
    "article",
    "@container group/card slide-in-up relative flex h-full cursor-pointer flex-col gap-4 overflow-hidden rounded-2xl border border-neutral-400 bg-neutral-50 p-5 shadow-sm transition-all duration-300 ease-out hover:-translate-y-1 hover:border-neutral-500 hover:shadow-xl has-[a:focus-visible]:ring-2 has-[a:focus-visible]:ring-primary-500 has-[a:focus-visible]:ring-offset-2 motion-reduce:transition-none motion-reduce:hover:translate-y-0 sm:p-6",
  );
  ticketDiv.setAttribute("aria-labelledby", titleId);
  ticketDiv.dataset.status = ticket.status;
  ticketDiv.dataset.priority = ticket.priority;
  ticketDiv.dataset.ticketId = ticket.id;
  ticketDiv.style.animationDelay = `${Math.min(index, 8) * 60}ms`;

  const accent = el(
    "span",
    `absolute inset-y-0 left-0 w-1 transition-all duration-300 group-hover/card:w-1.5 ${statusConfig.accent}`,
  );
  accent.setAttribute("aria-hidden", "true");

  // Header: ID + status / priority chips
  const ticketHeader = el(
    "div",
    "flex flex-wrap items-center justify-between gap-x-3 gap-y-2",
  );
  const ticketIdContainer = createTicketIdElement(ticket.id);

  const chipsContainer = el("div", "flex flex-wrap items-center gap-1.5");
  chipsContainer.append(
    createChipElement(ticket.status_label ?? ticket.status, statusConfig),
    createChipElement(
      `${ticket.priority_label ?? ticket.priority} priority`,
      priorityConfig,
    ),
  );
  ticketHeader.append(ticketIdContainer, chipsContainer);

  // Body: title + description
  const ticketBody = el("div", "flex flex-col gap-1.5");
  const ticketTitle = el(
    "h3",
    "line-clamp-2 font-sans text-lg font-semibold leading-snug text-foreground transition-colors duration-200 group-hover/card:text-secondary-700",
    ticket.title,
  );
  ticketTitle.id = titleId;
  ticketTitle.title = ticket.title;

  const ticketDescription = el(
    "p",
    "line-clamp-3 font-sans text-sm leading-relaxed text-neutral-900",
    ticket.description || "Tanpa deskripsi.",
  );
  ticketBody.append(ticketTitle, ticketDescription);

  // People: requester → assignee, stacked on narrow cards
  const ticketUserInfoContainer = el(
    "div",
    "flex flex-col gap-3 rounded-xl bg-neutral-300 p-3 @sm:flex-row @sm:items-center",
  );
  const ticketRequesterContainer = createPersonElement(ticket.requester, {
    caption: "Dibuat oleh",
    fallbackName: "Pengguna tidak dikenal",
    captionNode: createTimeElement(ticket.created_at),
  });

  const arrowIcon = createIcon(
    "arrow-right",
    "w-4 h-4 shrink-0 self-center rotate-90 text-neutral-700 transition-transform duration-300 @sm:rotate-0 @sm:group-hover/card:translate-x-0.5",
  );

  const ticketTaker = createPersonElement(ticket.assignee, {
    caption: "Ditangani oleh",
    fallbackName: "Menunggu koordinator",
    captionNode: ticket.assignee
      ? document.createTextNode(ticket.assignee.role)
      : null,
  });
  ticketUserInfoContainer.append(
    ticketRequesterContainer,
    arrowIcon,
    ticketTaker,
  );

  // Footer: comments, last update, CTA
  const ticketFooter = el(
    "div",
    "mt-auto flex flex-wrap items-center gap-x-4 gap-y-3 border-t border-neutral-400 pt-4",
  );

  const ticketMeta = el(
    "div",
    "flex items-center gap-4 font-sans text-xs text-neutral-800",
  );

  const commentsCount = ticket.messages_count ?? 0;
  const ticketCommentsCount = el("span", "inline-flex items-center gap-1.5");
  ticketCommentsCount.append(
    createIcon("message-square", "w-4 h-4"),
    el(
      "span",
      "",
      `${commentsCount} ${commentsCount === 1 ? "reply" : "replies"}`,
    ),
  );

  const ticketLastUpdated = el("span", "inline-flex items-center gap-1.5 mt-3 mb-3");
  ticketLastUpdated.append(
    createIcon("clock", "w-4 h-4"),
    createTimeElement(ticket.updated_at, "Diperbarui "),
  );
  ticketMeta.append(ticketCommentsCount, ticketLastUpdated);

  const CTAButton = cloneTemplate("tpl-button-view-ticket");
  CTAButton.href = ticket.detail_url ?? "#";
  CTAButton.setAttribute("aria-label", `Lihat tiket: ${ticket.title}`);

  ticketFooter.append(ticketMeta, CTAButton);

  ticketDiv.append(
    accent,
    ticketHeader,
    ticketBody,
    ticketUserInfoContainer,
    ticketFooter,
  );

  // The whole card opens the ticket. The "View details" link stays the one
  // keyboard/screen-reader target, so this handler only covers mouse/touch.
  ticketDiv.addEventListener("click", (event) => {
    if (event.target.closest("a, button")) return;
    // Let people select text on the card without opening it
    if (window.getSelection()?.toString()) return;

    if (event.ctrlKey || event.metaKey) {
      window.open(CTAButton.href, "_blank", "noopener");
    } else {
      window.location.href = CTAButton.href;
    }
  });

  return ticketDiv;
}

function createTicketsEmptyState({ icon, title, message, action }) {
  const empty = el(
    "div",
    "col-span-full flex flex-col items-center justify-center gap-3 rounded-2xl border-2 border-dashed border-neutral-500 px-6 py-16 text-center",
  );
  const iconBox = el(
    "span",
    "flex h-14 w-14 items-center justify-center rounded-2xl bg-primary-100 text-primary-700",
  );
  iconBox.append(createIcon(icon, "w-7 h-7"));
  empty.append(
    iconBox,
    el("h3", "font-sans text-lg font-semibold text-foreground", title),
    el("p", "max-w-sm font-sans text-sm text-neutral-800", message),
  );
  if (action) empty.append(action);
  return empty;
}

function createClearFiltersButton() {
  const button = cloneTemplate("tpl-button-clear-filters");
  button.addEventListener("click", clearTicketQuery);
  return button;
}


/* ============================ TICKET STATS ============================ */

const STATUS_STAT_KEYS = ["open", "in_progress", "resolved", "closed"];
const PRIORITY_STAT_KEYS = ["high", "normal", "low"];

function toPercent(value, total) {
  return total ? Math.round((value / total) * 100) : 0;
}

function animateCount(node, target) {
  if (prefersReducedMotion.matches || target === 0) {
    node.textContent = target;
    return;
  }

  const duration = 700;
  const start = performance.now();
  const step = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - Math.pow(1 - progress, 3);
    node.textContent = Math.round(target * eased);
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function growBar(bar, percent) {
  bar.style.width = "0%";
  requestAnimationFrame(() =>
    requestAnimationFrame(() => {
      bar.style.width = `${percent}%`;
    }),
  );
}

function createPanelHeader(title, subtitle, aside) {
  const header = el("div", "flex flex-wrap items-end justify-between gap-2");
  const text = el("div", "flex flex-col");
  text.append(
    el("h2", "font-sans text-base font-semibold text-foreground", title),
    el("p", "font-sans text-xs text-neutral-800", subtitle),
  );
  header.append(text);
  if (aside) header.append(aside);
  return header;
}

function createStatusStatElement(stat, total) {

  const config = TICKET_STATUS_CONFIG[stat.key] ?? TICKET_STATUS_CONFIG.open;
  const percent = toPercent(stat.value, total);

  const card = el(
    "div",
    "flex w-full flex-col gap-3 rounded-2xl border border-neutral-400 bg-neutral-50 p-4 sm:p-5",
  );

  const iconBox = el(
    "span",
    `flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${config.chip} ${config.iconColor}`,
  );
  iconBox.append(createIcon(stat.icon ?? config.icon, "w-5 h-5"));

  const value = el(
    "span",
    "font-sans text-3xl font-bold leading-none tabular-nums text-foreground",
    "0",
  );
  const label = el(
    "span",
    "font-sans text-sm font-semibold text-neutral-900",
    stat.label,
  );
  const text = el("div", "flex flex-col gap-1.5");
  text.append(value, label);

  const meter = el("div", "flex items-center gap-2");
  const track = el(
    "div",
    "h-1.5 flex-1 overflow-hidden rounded-full bg-neutral-400/70",
  );
  const bar = el(
    "div",
    `h-full rounded-full transition-[width] duration-700 ease-out motion-reduce:transition-none ${config.accent}`,
  );
  track.append(bar);
  meter.append(
    track,
    el(
      "span",
      "w-9 text-right font-sans text-xs font-medium tabular-nums text-neutral-800",
      `${percent}%`,
    ),
  );

  card.append(iconBox, text, meter);
  animateCount(value, stat.value);
  growBar(bar, percent);
  return card;
}

function createPriorityStatElement(stat, total) {
  const config =
    TICKET_PRIORITY_CONFIG[stat.key] ?? TICKET_PRIORITY_CONFIG.normal;
  const percent = toPercent(stat.value, total);

  const row = el(
    "div",
    "flex min-h-11 w-full items-center gap-3 rounded-xl px-3 py-2.5",
  );

  const iconBox = el(
    "span",
    `flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border ${config.chip} ${config.iconColor}`,
  );
  iconBox.append(createIcon(stat.icon ?? config.icon, "w-4 h-4"));

  const label = el(
    "span",
    "min-w-0 flex-1 truncate font-sans text-sm font-semibold text-foreground",
    stat.label,
  );
  const value = el(
    "span",
    "font-sans text-base font-bold tabular-nums text-foreground",
    "0",
  );
  const share = el(
    "span",
    "w-9 text-right font-sans text-xs tabular-nums text-neutral-800",
    `${percent}%`,
  );

  row.append(iconBox, label, value, share);
  animateCount(value, stat.value);
  return row;
}

// One bar split into segments, showing the priority mix at a glance
function createPriorityDistributionBar(stats, total) {
  const bar = el(
    "div",
    "flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-neutral-400/70",
  );
  bar.setAttribute("role", "img");
  bar.setAttribute(
    "aria-label",
    `Priority distribution: ${stats
      .map((stat) => `${stat.label} ${toPercent(stat.value, total)}%`)
      .join(", ")}`,
  );

  stats
    .filter((stat) => stat.value > 0)
    .forEach((stat) => {
      const config =
        TICKET_PRIORITY_CONFIG[stat.key] ?? TICKET_PRIORITY_CONFIG.normal;
      const segment = el(
        "span",
        `h-full transition-[width] duration-700 ease-out first:rounded-l-full last:rounded-r-full motion-reduce:transition-none ${config.accent}`,
      );
      segment.title = `${stat.label}: ${stat.value}`;
      growBar(segment, toPercent(stat.value, total));
      bar.append(segment);
    });
  return bar;
}

// Built from the skeleton component (<template id="tpl-stats-skeleton"> in helpdesk.html)
function createStatsSkeleton() {
  return cloneTemplateContent("tpl-stats-skeleton");
}

function createStatsErrorState() {
  const error = el(
    "div",
    "flex flex-col items-start gap-3 rounded-3xl border border-red-100/40 bg-red-100/5 p-5 sm:flex-row sm:items-center",
  );
  const text = el("div", "flex flex-1 items-center gap-3");
  text.append(
    createIcon("triangle-alert", "w-5 h-5 shrink-0 text-red-100"),
    el(
      "p",
      "font-sans text-sm text-foreground",
      "Statistik tiketmu gagal dimuat.",
    ),
  );

  const retryButton = cloneTemplate("tpl-button-retry");
  retryButton.addEventListener("click", initTicketStats);

  error.append(text, retryButton);
  return error;
}

function renderTicketStats(stats) {
  const statsByKey = Object.fromEntries(stats.map((stat) => [stat.key, stat]));
  const statusStats = STATUS_STAT_KEYS.map((key) => statsByKey[key]).filter(Boolean);
  const priorityStats = PRIORITY_STAT_KEYS.map((key) => statsByKey[key]).filter(Boolean);

  const total = statusStats.reduce((sum, stat) => sum + stat.value, 0);

  const layout = el(
    "div",
    "grid gap-4 xl:grid-cols-[minmax(0,2fr)_minmax(0,1fr)]",
  );

  // Status panel
  const statusPanel = el(
    "section",
    "flex flex-col gap-4 rounded-3xl border border-neutral-400 bg-neutral-300 p-4 sm:p-6",
  );
  statusPanel.setAttribute("aria-labelledby", "ticketStatusStatsTitle");

  const totalBadge = el(
    "span",
    "inline-flex items-baseline gap-1.5 rounded-full border border-neutral-400 bg-neutral-50 px-3 py-1 font-sans text-xs text-neutral-800",
  );
  const totalValue = el("strong", "text-sm font-bold tabular-nums text-foreground", "0");
  totalBadge.append(totalValue, el("span", "", "tiket total"));
  animateCount(totalValue, total);

  const statusHeader = createPanelHeader(
    "Tiket per status",
    "",
    totalBadge,
  );
  statusHeader.querySelector("h2").id = "ticketStatusStatsTitle";

  const statusGrid = el("div", "grid grid-cols-2 gap-3 md:grid-cols-4");
  statusGrid.append(
    ...statusStats.map((stat) => createStatusStatElement(stat, total)),
  );
  statusPanel.append(statusHeader, statusGrid);

  // Priority panel
  const priorityPanel = el(
    "section",
    "flex flex-col gap-4 rounded-3xl border border-neutral-400 bg-neutral-300 p-4 sm:p-6",
  );
  priorityPanel.setAttribute("aria-labelledby", "ticketPriorityStatsTitle");

  const priorityHeader = createPanelHeader(
    "Tiket per prioritas",
    "",
  );
  priorityHeader.querySelector("h2").id = "ticketPriorityStatsTitle";

  const priorityList = el("div", "grid gap-1 sm:grid-cols-3 xl:grid-cols-1");
  priorityList.append(
    ...priorityStats.map((stat) => createPriorityStatElement(stat, total)),
  );
  priorityPanel.append(
    priorityHeader,
    createPriorityDistributionBar(priorityStats, total),
    priorityList,
  );

  layout.append(statusPanel, priorityPanel);

  ticketStatsContainer.replaceChildren(layout);
  renderLucideIcons(ticketStatsContainer);
}

// `silent` refreshes the numbers in place, without flashing the skeleton
async function initTicketStats({ silent = false } = {}) {
  if (!ticketStatsContainer || !STATS_API_URL) return;

  ticketStatsContainer.setAttribute("aria-busy", "true");
  if (!silent) ticketStatsContainer.replaceChildren(createStatsSkeleton());

  try {
    renderTicketStats(await fetchTicketStats());
  } catch (error) {
    console.error(error);
    ticketStatsContainer.replaceChildren(createStatsErrorState());
    renderLucideIcons(ticketStatsContainer);
  } finally {
    ticketStatsContainer.removeAttribute("aria-busy");
  }
}

/* =============================== TICKETS =============================== */

const ticketSearchInput = document.getElementById("ticketsSearch");
const ticketStatusInput = document.getElementById("tickets-status-dropdown");
const ticketPriorityInput = document.getElementById("tickets-priority-dropdown");
const ticketSortInput = document.getElementById("tickets-sorting-dropdown");
const ticketsResultCount = document.getElementById("ticketsResultCount");
const ticketsPagination = document.getElementById("ticketsPagination");
const ticketsActiveFilters = document.getElementById("ticketsActiveFilters");

const SEARCH_CHIP_CONFIG = {
  icon: "search",
  chip: "border-neutral-500 bg-neutral-50",
  iconColor: "text-neutral-800",
};

const DEFAULT_TICKET_SORT = "-created_at";
const SEARCH_DEBOUNCE_MS = 300;

function getTicketQuery() {
  return {
    status: ticketStatusInput?.value ?? "",
    priority: ticketPriorityInput?.value ?? "",
    sort: ticketSortInput?.value || DEFAULT_TICKET_SORT,
    search: ticketSearchInput?.value.trim() ?? "",
  };
}

function hasActiveTicketFilters(query) {
  return Boolean(query.status || query.priority || query.search);
}

function buildTicketParams(query, page = 1) {
  const params = new URLSearchParams();
  if (query.status) params.set("status", query.status);
  if (query.priority) params.set("priority", query.priority);
  if (query.sort !== DEFAULT_TICKET_SORT) params.set("sort", query.sort);
  if (query.search) params.set("search", query.search);
  // Page 1 stays out of the URL, so a plain visit keeps a clean address
  if (page > 1) params.set("page", page);
  return params;
}

function syncUrlWithTicketParams(params) {
  const queryString = params.toString();
  const url = queryString
    ? `${location.pathname}?${queryString}`
    : location.pathname;
  history.replaceState(null, "", url);
}

function debounce(callback, delay) {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => callback(...args), delay);
  };
}

function resetDropdown(hiddenInput) {
  if (!hiddenInput) return;
  hiddenInput.value = "";

  const label = hiddenInput
    .closest(".custom-dropdown")
    ?.querySelector(".dropdown-label");
  if (label) {
    label.textContent = label.dataset.placeholder;
    label.classList.add("text-foreground/80");
  }
}

function clearTicketQuery() {
  resetDropdown(ticketStatusInput);
  resetDropdown(ticketPriorityInput);
  if (ticketSearchInput) ticketSearchInput.value = "";
  ticketSearchInput?.focus();
  loadTickets();
}

// Reuse the label the dropdown already shows for an option, instead of
// keeping a second copy of the labels in JS
function getDropdownOptionLabel(hiddenInput, value) {
  return hiddenInput
    ?.closest(".custom-dropdown")
    ?.querySelector(`.dropdown-item[data-value="${CSS.escape(value)}"]`)
    ?.dataset.label ?? value;
}

// Removable chip, styled like the chips design-system component and colored
// like the status/priority chips on the ticket cards
function createFilterChip({ label, config, removeLabel, onRemove }) {
  const chip = el(
    "button",
    `group/chip inline-flex min-h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-full border py-1 pl-3 pr-1.5 font-sans text-sm font-semibold text-foreground outline-none transition-all duration-200 hover:shadow-sm focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 active:scale-[0.97] ${config.chip}`,
  );
  chip.type = "button";
  chip.setAttribute("aria-label", removeLabel);
  chip.title = removeLabel;

  const removeIcon = el(
    "span",
    "flex h-6 w-6 items-center justify-center rounded-full text-neutral-800 transition-colors duration-200 group-hover/chip:bg-neutral-900/10 group-hover/chip:text-foreground",
  );
  removeIcon.append(createIcon("x", "w-3.5 h-3.5"));

  chip.append(
    createIcon(config.icon, `w-4 h-4 ${config.iconColor}`),
    el("span", "max-w-48 truncate", label),
    removeIcon,
  );

  chip.addEventListener("click", () => {
    const index = [...ticketsActiveFilters.children].indexOf(chip);
    onRemove();
    loadTickets();

    // The chip is gone after re-rendering; keep keyboard focus nearby
    const remaining = ticketsActiveFilters.querySelectorAll("button");
    (remaining[Math.min(index, remaining.length - 1)] ?? ticketSearchInput)?.focus();
  });

  return chip;
}

function renderActiveFilterChips(query) {
  if (!ticketsActiveFilters) return;

  const chips = [];

  if (query.status) {
    const label = getDropdownOptionLabel(ticketStatusInput, query.status);
    chips.push(
      createFilterChip({
        label,
        config: TICKET_STATUS_CONFIG[query.status] ?? TICKET_STATUS_CONFIG.open,
        removeLabel: `Hapus filter status: ${label}`,
        onRemove: () => resetDropdown(ticketStatusInput),
      }),
    );
  }

  if (query.priority) {
    const label = getDropdownOptionLabel(ticketPriorityInput, query.priority);
    chips.push(
      createFilterChip({
        label: `${label} priority`,
        config:
          TICKET_PRIORITY_CONFIG[query.priority] ?? TICKET_PRIORITY_CONFIG.normal,
        removeLabel: `Hapus filter prioritas: ${label}`,
        onRemove: () => resetDropdown(ticketPriorityInput),
      }),
    );
  }

  if (query.search) {
    chips.push(
      createFilterChip({
        label: `“${query.search}”`,
        config: SEARCH_CHIP_CONFIG,
        removeLabel: `Hapus pencarian: ${query.search}`,
        onRemove: () => {
          ticketSearchInput.value = "";
        },
      }),
    );
  }

  // With several filters, one action to undo them all saves clicks
  if (chips.length > 1) {
    const clearAll = cloneTemplate("tpl-button-clear-all");
    clearAll.addEventListener("click", clearTicketQuery);
    chips.push(clearAll);
  }

  ticketsActiveFilters.replaceChildren(...chips);
  renderLucideIcons(ticketsActiveFilters);
}

function renderTicketsResultCount(pagination, totalCount, query) {
  if (!ticketsResultCount) return;

    ticketsResultCount.textContent = totalCount === 0
    ? ""
    : formatPageRange(pagination, hasActiveTicketFilters(query) ? "tiket yang cocok" : "tiket");
}

function renderTicketsPagination(pagination, query) {
  if (!ticketsPagination) return;
  ticketsPagination.replaceChildren(
    createPagination({
      page: pagination.page,
      totalPages: pagination.total_pages,
      label: "Halaman tiket",
      hrefFor: (page) => {
        const queryString = buildTicketParams(query, page).toString();
        return queryString ? `${location.pathname}?${queryString}` : location.pathname;
      },
      onChange: goToTicketPage,
    }),
  );
}

// After switching pages, bring the list (not the pager at the bottom) into view
// and move focus there, so keyboard and screen reader users start at the top
async function goToTicketPage(page) {
  await loadTickets({ page });
  ticketsContainer.scrollIntoView({ behavior: prefersReducedMotion.matches ? "auto" : "smooth", block: "start" });
  ticketsContainer.focus({ preventScroll: true });
}

function renderTickets(tickets, totalCount, query, pagination) {
  let content;

  if (tickets.length) {
    content = tickets.map((ticket, index) =>
      createTicketsCardElement(ticket, index),
    );
  } else if (totalCount === 0) {
    // The user has no tickets at all
    content = [
      createTicketsEmptyState({
        icon: "inbox",
        title: "Belum ada tiket",
        message: "Keluhan, laporan bug, atau masukan yang kamu kirim akan muncul di sini.",
      }),
    ];
  } else {
    // Tickets exist, but the filter/search hides all of them
    content = [
      createTicketsEmptyState({
        icon: "search-x",
        title: "Nggak ada tiket yang cocok",
        message: "Coba kata kunci atau filter lain.",
        action: createClearFiltersButton(),
      }),
    ];
  }

  ticketsContainer.replaceChildren(...content);
  renderLucideIcons(ticketsContainer);
  renderTicketsResultCount(pagination, totalCount, query);
  renderTicketsPagination(pagination, query);
}

let ticketsRequestController = null;
// The page the list is showing; the server may correct it (e.g. past the last page)
let currentTicketPage = 1;

// Any change to filters, sort or search starts again at page 1 (the default);
// paging and refreshes pass the page explicitly
async function loadTickets({ page = 1 } = {}) {
  const query = getTicketQuery();
  const params = buildTicketParams(query, page);
  syncUrlWithTicketParams(params);
  // Chips update right away, without waiting for the server
  renderActiveFilterChips(query);

  ticketsRequestController?.abort();
  const controller = new AbortController();
  ticketsRequestController = controller;

  ticketsContainer.setAttribute("aria-busy", "true");

  try {
    const { tickets, totalCount, pagination } = await fetchTickets(
      params,
      controller.signal,
    );
    currentTicketPage = pagination.page;
    // Keep the URL on the page actually shown (a too-high ?page= snaps back)
    if (pagination.page !== page) syncUrlWithTicketParams(buildTicketParams(query, pagination.page));
    renderTickets(tickets, totalCount, query, pagination);
  } catch (error) {
    if (error.name === "AbortError") return;

    console.error(error);
    window.showToast?.({
      type: "error",
      title: "Tiket gagal dimuat",
      message: error.message,
    });
  } finally {
    // Only the latest request may clear the loading state
    if (ticketsRequestController === controller) {
      ticketsContainer.removeAttribute("aria-busy");
    }
  }
}

function bindTicketControls() {

  // New filters, sort or search: back to page 1 (loadTickets' default)
  ticketStatusInput?.addEventListener("change", () => loadTickets());
  ticketPriorityInput?.addEventListener("change", () => loadTickets());
  ticketSortInput?.addEventListener("change", () => loadTickets());

  ticketSearchInput?.addEventListener(
    "input",
    debounce(() => loadTickets(), SEARCH_DEBOUNCE_MS),
  );
}

function initTickets() {

  if (!ticketsContainer || !TICKETS_API_URL) return;

  bindTicketControls();
  // Open on the page in the URL (a refreshed or shared link keeps its page)
  const initialPage = Number(new URLSearchParams(location.search).get("page")) || 1;
  loadTickets({ page: initialPage });
}

/* =========================== CREATED TICKETS =========================== */

// Mirrors the server's filtering (apply_ticket_query in views.py)
function ticketMatchesQuery(ticket, query) {
  if (query.status && ticket.status !== query.status) return false;
  if (query.priority && ticket.priority !== query.priority) return false;
  if (query.search) {
    const needle = query.search.toLowerCase();
    return (
      ticket.title.toLowerCase().includes(needle) ||
      (ticket.description ?? "").toLowerCase().includes(needle)
    );
  }
  return true;
}

// Draws the eye to the new card, then lets the highlight fade
function highlightTicketCard(card) {
  card.classList.add("ring-2", "ring-primary-500", "ring-offset-2");
  card.scrollIntoView({ behavior: prefersReducedMotion.matches ? "auto" : "smooth", block: "nearest" });
  setTimeout(() => card.classList.remove("ring-2", "ring-primary-500", "ring-offset-2"), 2400);
}

async function handleTicketCreated(event) {
  const { ticket } = event.detail;
  const query = getTicketQuery();

  // The counts change whether or not the ticket is visible
  initTicketStats({ silent: true });

  if (!ticketsContainer) return;

  if (!ticketMatchesQuery(ticket, query)) {
    window.showToast?.({
      type: "info",
      title: "Tiket barumu tersembunyi",
      message: "Tiketnya nggak cocok dengan filter atau pencarian saat ini. Hapus filternya untuk melihat.",
    });
    return;
  }

  // Newest first (the default): the new ticket is first on page 1, so go there.
  // Any other sort: the server decides where it lands; stay on this page.
  const page = query.sort === DEFAULT_TICKET_SORT ? 1 : currentTicketPage;
  await loadTickets({ page });

  const card = ticketsContainer.querySelector(
    `article[data-ticket-id="${CSS.escape(ticket.id)}"]`,
  );
  if (card) highlightTicketCard(card);
}

function init() {

  document.addEventListener("helpdesk:ticket-created", handleTicketCreated);

  initTicketStats();
  initTickets();

}

init();
