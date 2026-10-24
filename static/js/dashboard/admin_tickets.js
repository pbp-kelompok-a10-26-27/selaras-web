import "./../components/toast/toast.js";
import {
  TICKET_PRIORITY_CONFIG,
  TICKET_STATUS_CONFIG,
  cloneTemplate,
  createAvatarElement,
  createChipElement,
  createIcon,
  createTicketIdElement,
  createTimeElement,
  el,
  renderLucideIcons,
  setButtonLoading,
} from "../helpdesk/shared.js";

const root = document.getElementById("adminTickets");

const LIST_URL = root?.dataset.listUrl;
const STATS_URL = root?.dataset.statsUrl;
const ZERO_UUID = "00000000-0000-0000-0000-000000000000";
const csrfToken = document.getElementById("dashboardCsrfToken")?.value ?? "";

const statsContainer = document.getElementById("adminTicketStats");
const searchInput = document.getElementById("adminTicketsSearch");
const statusInput = document.getElementById("admin-tickets-status");
const priorityInput = document.getElementById("admin-tickets-priority");
const assignmentInput = document.getElementById("admin-tickets-assignment");
const sortInput = document.getElementById("admin-tickets-sort");
const activeFilters = document.getElementById("adminTicketsActiveFilters");
const resultCount = document.getElementById("adminTicketsResultCount");

const assignedSection = document.getElementById("assignedSection");
const assignedList = document.getElementById("assignedList");
const assignedCount = document.getElementById("assignedCount");
const othersSection = document.getElementById("othersSection");
const othersList = document.getElementById("othersList");
const othersCount = document.getElementById("othersCount");
const loadMoreButton = document.getElementById("adminTicketsLoadMore");
const refreshButton = document.getElementById("adminTicketsRefresh");

const deleteConfirmButton = document.getElementById("deleteTicketConfirm");

// Must match DEFAULT_SORT in apps/helpdesk/views.py
const DEFAULT_SORT = "-created_at";
const SEARCH_DEBOUNCE_MS = 300;
const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

const ASSIGNMENT_CHIP_CONFIG = {
  me: { icon: "user-check", chip: "border-orange-100/50 bg-orange-100/15", iconColor: "text-orange-100" },
  unassigned: { icon: "inbox", chip: "border-yellow-200/70 bg-yellow-100/40", iconColor: "text-secondary-700" },
  others: { icon: "user-round", chip: "border-neutral-500 bg-neutral-50", iconColor: "text-neutral-800" },
};
const SEARCH_CHIP_CONFIG = { icon: "search", chip: "border-neutral-500 bg-neutral-50", iconColor: "text-neutral-800" };

// What the lists currently show, so actions can update counts without refetching
const listState = { assigned: 0, othersTotal: 0, othersShown: 0, totalCount: 0, page: 1 };

/* ================================ REQUESTS ================================ */

async function readJson(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json"))
    throw new Error("Server did not return JSON. Your session may be expired");
  return response.json();
}

async function getJson(url, signal) {
  const response = await fetch(url, { headers: { Accept: "application/json" }, signal });
  if (!response.ok) throw new Error(`Request failed (${response.status})`);
  return readJson(response);
}

async function postJson(url) {
  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json", "X-CSRFToken": csrfToken },
  });
  return { response, data: await readJson(response) };
}

const ticketUrl = (template, ticketId) => template.replace(ZERO_UUID, ticketId);

/* ================================== STATS ================================== */

const KPI_CARDS = [
  { key: "assigned_to_me", label: "Assigned to you", hint: "open or in progress", icon: "user-check", tone: "border-orange-100/50 bg-orange-100/15 text-orange-100" },
  { key: "unassigned", label: "Unassigned", hint: "waiting for a coordinator", icon: "inbox", tone: "border-yellow-200/70 bg-yellow-100/40 text-secondary-700" },
  { key: "high_active", label: "High priority open", hint: "handle these first", icon: "arrow-up", tone: "border-red-100/40 bg-red-100/10 text-red-100" },
  { key: "resolved_week", label: "Resolved this week", hint: "in the last 7 days", icon: "circle-check", tone: "border-primary-500/50 bg-primary-200 text-primary-700" },
];

function toPercent(value, total) {
  return total ? Math.round((value / total) * 100) : 0;
}

function animateCount(node, target) {
  if (prefersReducedMotion.matches || target === 0) {
    node.textContent = target;
    return;
  }
  const start = performance.now();
  const step = (now) => {
    const progress = Math.min((now - start) / 700, 1);
    node.textContent = Math.round(target * (1 - Math.pow(1 - progress, 3)));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

// Bars render at 0 and grow to their width on the next frame
function growWidth(node, percent) {
  node.style.width = "0%";
  requestAnimationFrame(() => requestAnimationFrame(() => (node.style.width = `${percent}%`)));
}

function createKpiCard(card, value) {
  const item = el("div", "flex flex-col gap-3 rounded-2xl border border-neutral-400 bg-neutral-50 p-4 sm:p-5");
  const top = el("div", "flex items-center gap-3");
  const iconBox = el("span", `flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${card.tone}`);
  iconBox.append(createIcon(card.icon, "w-5 h-5"));
  top.append(iconBox, el("dt", "font-sans text-sm font-semibold leading-tight text-neutral-900", card.label));

  const valueEl = el("dd", "font-sans text-3xl font-bold leading-none tabular-nums text-foreground", "0");
  animateCount(valueEl, value);

  item.append(top, valueEl, el("dd", "font-sans text-xs text-neutral-800", card.hint));
  return item;
}

function createPanel(title, subtitle) {
  const panel = el("section", "flex flex-col gap-4 rounded-2xl border border-neutral-400 bg-neutral-50 p-4 sm:p-5");
  const header = el("div", "flex flex-wrap items-baseline justify-between gap-2");
  header.append(
    el("h3", "font-sans text-sm font-semibold text-foreground", title),
    el("p", "font-sans text-xs text-neutral-800", subtitle),
  );
  panel.append(header);
  return panel;
}

// All tickets by status: one segmented bar + a legend
function createStatusPanel(rows, total) {
  const panel = createPanel("All tickets by status", `${total} ${total === 1 ? "ticket" : "tickets"} in total`);

  const bar = el("div", "flex h-3 w-full gap-0.5 overflow-hidden rounded-full bg-neutral-400/70");
  bar.setAttribute("role", "img");
  bar.setAttribute("aria-label", `Status breakdown: ${rows.map((r) => `${r.label} ${r.value}`).join(", ")}`);
  rows.filter((r) => r.value > 0).forEach((row) => {
    const segment = el("span", `h-full transition-[width] duration-700 ease-out first:rounded-l-full last:rounded-r-full motion-reduce:transition-none ${(TICKET_STATUS_CONFIG[row.key] ?? TICKET_STATUS_CONFIG.open).accent}`);
    segment.title = `${row.label}: ${row.value}`;
    growWidth(segment, toPercent(row.value, total));
    bar.append(segment);
  });

  const legend = el("dl", "grid grid-cols-2 gap-x-4 gap-y-2 sm:grid-cols-4");
  rows.forEach((row) => {
    const config = TICKET_STATUS_CONFIG[row.key] ?? TICKET_STATUS_CONFIG.open;
    const item = el("div", "flex flex-col");
    const label = el("dt", "flex items-center gap-1.5 font-sans text-xs text-neutral-900");
    label.append(el("span", `h-2.5 w-2.5 shrink-0 rounded-full ${config.accent}`), el("span", "", row.label));
    const value = el("dd", "font-sans text-sm font-semibold tabular-nums text-foreground");
    value.append(`${row.value} `, el("span", "font-normal text-neutral-800", `· ${toPercent(row.value, total)}%`));
    item.append(label, value);
    legend.append(item);
  });

  panel.append(bar, legend);
  return panel;
}

// Open workload by priority: one bar per priority, scaled to the largest
function createPriorityPanel(rows, activeTotal) {
  const panel = createPanel("Open workload by priority", `${activeTotal} open or in progress`);
  const max = Math.max(1, ...rows.map((r) => r.value));

  const list = el("dl", "flex flex-col gap-3");
  rows.forEach((row) => {
    const config = TICKET_PRIORITY_CONFIG[row.key] ?? TICKET_PRIORITY_CONFIG.normal;
    const item = el("div", "grid grid-cols-[6.5rem_minmax(0,1fr)_2.5rem] items-center gap-3");
    const label = el("dt", "flex items-center gap-2 font-sans text-sm font-semibold text-foreground");
    label.append(createIcon(config.icon, `w-4 h-4 ${config.iconColor}`), el("span", "", row.label));
    const track = el("dd", "h-2.5 overflow-hidden rounded-full bg-neutral-400/70");
    const fill = el("span", `block h-full rounded-full transition-[width] duration-700 ease-out motion-reduce:transition-none ${config.accent}`);
    growWidth(fill, toPercent(row.value, max));
    track.append(fill);
    item.append(label, track, el("dd", "text-right font-sans text-sm font-semibold tabular-nums text-foreground", String(row.value)));
    list.append(item);
  });

  panel.append(list);
  return panel;
}

function renderStats(stats) {
  const kpis = el("dl", "grid grid-cols-2 gap-3 lg:grid-cols-4");
  KPI_CARDS.forEach((card) => kpis.append(createKpiCard(card, stats.kpis[card.key] ?? 0)));

  const panels = el("div", "grid gap-3 lg:grid-cols-2");
  panels.append(
    createStatusPanel(stats.status, stats.kpis.total),
    createPriorityPanel(stats.priority, stats.kpis.active),
  );

  const wrapper = el("div", "flex flex-col gap-3");
  wrapper.append(kpis, panels);
  statsContainer.replaceChildren(wrapper);
  renderLucideIcons(statsContainer);

  // Keep the sidebar's Helpdesk count in step (sidebar.js)
  const mine = stats.kpis.assigned_to_me;
  window.setSidebarBadge?.("helpdesk", mine, `${mine} active ticket${mine === 1 ? "" : "s"} assigned to you`);
}

async function loadStats() {
  if (!statsContainer || !STATS_URL) return;
  statsContainer.setAttribute("aria-busy", "true");
  try {
    renderStats(await getJson(STATS_URL));
  } catch (error) {
    console.error(error);
    const message = el("div", "flex items-center gap-3 rounded-2xl border border-red-100/40 bg-red-100/5 p-4 font-sans text-sm text-foreground");
    message.append(createIcon("triangle-alert", "w-5 h-5 shrink-0 text-red-100"), el("span", "", "Couldn't load ticket statistics. Use Refresh to try again."));
    statsContainer.replaceChildren(message);
    renderLucideIcons(statsContainer);
  } finally {
    statsContainer.removeAttribute("aria-busy");
  }
}

/* =============================== TICKET ROWS =============================== */

function highlight(node) {
  node.classList.add("ring-2", "ring-primary-500", "ring-offset-2");
  setTimeout(() => node.classList.remove("ring-2", "ring-primary-500", "ring-offset-2"), 2200);
}

function createTicketRow(ticket) {
  const statusConfig = TICKET_STATUS_CONFIG[ticket.status] ?? TICKET_STATUS_CONFIG.open;
  const priorityConfig = TICKET_PRIORITY_CONFIG[ticket.priority] ?? TICKET_PRIORITY_CONFIG.normal;
  const titleId = `admin-ticket-${ticket.id}`;

  const item = el("li", "slide-in-up transition-all duration-200 motion-reduce:transition-none");
  item.dataset.ticketId = ticket.id;

  // Wide screens: one table-like row (columns match the headings in the template).
  // Smaller screens: a stacked card; `xl:contents` lets the meta wrapper's cells join the grid.
  const row = el(
    "article",
    `group/row relative grid grid-cols-1 gap-3 overflow-hidden rounded-2xl border border-neutral-400 bg-neutral-50 py-4 pr-4 pl-5 outline-none transition-all duration-200 hover:border-neutral-500 hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary-500 sm:pr-5 sm:pl-6 xl:grid-cols-[minmax(0,1fr)_7.5rem_7.5rem_11rem_8rem_11rem] xl:items-center xl:gap-4 ${ticket.detail_url ? "cursor-pointer" : ""}`,
  );
  row.setAttribute("aria-labelledby", titleId);
  row.tabIndex = -1;

  const accent = el("span", `absolute inset-y-0 left-0 w-1 transition-all duration-200 group-hover/row:w-1.5 ${statusConfig.accent}`);
  accent.setAttribute("aria-hidden", "true");

  // Ticket: ID, subject, requester
  const main = el("div", "flex min-w-0 flex-col gap-1.5");
  const topLine = el("div", "flex flex-wrap items-center gap-2");
  topLine.append(createTicketIdElement(ticket.id));
  if (ticket.is_assigned_to_me) {
    topLine.append(el("span", "rounded-full border border-orange-100/50 bg-orange-100/15 px-2 py-0.5 font-sans text-[0.6875rem] font-semibold text-secondary-900", "Yours"));
  }

  const subject = ticket.detail_url
    ? el("a", "line-clamp-2 rounded-md font-sans text-base font-semibold leading-snug text-foreground outline-none hover:underline focus-visible:ring-2 focus-visible:ring-primary-500 xl:line-clamp-1", ticket.title)
    : el("h3", "line-clamp-2 font-sans text-base font-semibold leading-snug text-foreground xl:line-clamp-1", ticket.title);
  if (ticket.detail_url) subject.href = ticket.detail_url;
  subject.id = titleId;
  subject.title = ticket.title;

  const requester = el("p", "truncate font-sans text-xs text-neutral-800");
  requester.append(
    `by ${ticket.requester?.name ?? "Unknown user"}`,
    ticket.requester_email ? ` · ${ticket.requester_email}` : "",
    " · ",
    createTimeElement(ticket.created_at, "opened "),
  );
  main.append(topLine, subject, requester);

  // Status, priority, assignee, activity
  const meta = el("div", "flex flex-wrap items-center gap-x-4 gap-y-2 xl:contents");

  const statusCell = el("div", "xl:flex");
  statusCell.append(createChipElement(ticket.status_label, statusConfig));
  const priorityCell = el("div", "xl:flex");
  priorityCell.append(createChipElement(ticket.priority_label, priorityConfig));

  const assigneeCell = el("div", "flex min-w-0 items-center gap-2");
  assigneeCell.append(createAvatarElement(ticket.assignee, "h-7 w-7 text-[0.625rem]"));
  const assigneeName = el(
    "span",
    `truncate font-sans text-sm ${ticket.assignee ? "font-semibold text-foreground" : "italic text-neutral-800"}`,
    ticket.is_assigned_to_me ? "You" : ticket.assignee?.name ?? "Unassigned",
  );
  if (ticket.assignee) assigneeName.title = ticket.assignee.name;
  assigneeCell.append(el("span", "sr-only", "Assignee:"), assigneeName);

  const activityCell = el("div", "flex items-center gap-3 font-sans text-xs text-neutral-800 xl:flex-col xl:items-start xl:gap-0.5");
  const replies = el("span", "inline-flex items-center gap-1.5");
  const count = ticket.messages_count ?? 0;
  replies.append(createIcon("message-square", "w-3.5 h-3.5"), `${count} ${count === 1 ? "reply" : "replies"}`);
  const updated = el("span", "inline-flex items-center gap-1.5");
  updated.append(createIcon("clock", "w-3.5 h-3.5"), createTimeElement(ticket.updated_at, "updated "));
  activityCell.append(replies, updated);

  meta.append(statusCell, priorityCell, assigneeCell, activityCell);

  // Actions
  const actions = el("div", "flex items-center gap-2 border-t border-neutral-400 pt-3 xl:justify-end xl:border-0 xl:pt-0");
  if (ticket.can_assign_to_me) {
    const assignButton = cloneTemplate("tpl-button-assign");
    assignButton.setAttribute("aria-label", `Assign ticket ${ticket.title} to me`);
    assignButton.addEventListener("click", () => assignTicket(ticket, assignButton, item));
    actions.append(assignButton);
  }
  const deleteButton = cloneTemplate("tpl-button-delete");
  deleteButton.classList.add("ml-auto", "xl:ml-0");
  deleteButton.setAttribute("aria-label", `Delete ticket ${ticket.title}`);
  deleteButton.title = "Delete ticket";
  deleteButton.addEventListener("click", () => openDeleteDialog(ticket, item));
  actions.append(deleteButton);

  row.append(accent, main, meta, actions);

  // The whole row opens the ticket (once the detail page exists); buttons and links keep their own job
  if (ticket.detail_url) {
    row.addEventListener("click", (event) => {
      if (event.target.closest("a, button")) return;
      if (window.getSelection()?.toString()) return;
      if (event.ctrlKey || event.metaKey) window.open(ticket.detail_url, "_blank", "noopener");
      else window.location.href = ticket.detail_url;
    });
  }

  item.append(row);
  return item;
}

function createEmptyState({ icon, title, message, action }) {
  const empty = el("li", "flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-neutral-500 px-6 py-10 text-center");
  empty.dataset.emptyState = "";
  const iconBox = el("span", "flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-100 text-primary-700");
  iconBox.append(createIcon(icon, "w-6 h-6"));
  empty.append(
    iconBox,
    el("p", "font-sans text-sm font-semibold text-foreground", title),
    el("p", "max-w-md font-sans text-sm text-neutral-800", message),
  );
  if (action) empty.append(action);
  return empty;
}

function createActionButton(templateId, label, onClick) {
  const button = cloneTemplate(templateId);
  const text = button.querySelector("[data-button-text]");
  if (text && label) text.textContent = label;
  button.classList.add("mt-2");
  button.addEventListener("click", onClick);
  return button;
}

function assignedEmptyState(query) {
  if (hasActiveFilters(query)) {
    return createEmptyState({ icon: "search-x", title: "None of your tickets match", message: "Try a different search or filter." });
  }
  return createEmptyState({
    icon: "inbox",
    title: "Nothing assigned to you",
    message: "Take an unassigned ticket to start helping. You can only reply to tickets assigned to you.",
    action: createActionButton("tpl-button-show-unassigned", "", () => setDropdownValue(assignmentInput, "unassigned")),
  });
}

function othersEmptyState(query) {
  if (hasActiveFilters(query)) {
    return createEmptyState({
      icon: "search-x",
      title: "No other tickets match",
      message: "Try a different search or filter.",
      action: createActionButton("tpl-button-clear-filters", "", clearQuery),
    });
  }
  if (listState.totalCount === 0) {
    return createEmptyState({ icon: "inbox", title: "No tickets yet", message: "When users file tickets, they'll show up here." });
  }
  return createEmptyState({ icon: "inbox", title: "No other tickets", message: "Every ticket is assigned to you." });
}

function updateCounts(query = getQuery()) {
  assignedCount.textContent = listState.assigned;
  othersCount.textContent = listState.othersTotal;

  const shown = (assignedSection.hidden ? 0 : listState.assigned) + (othersSection.hidden ? 0 : listState.othersTotal);
  resultCount.textContent = hasActiveFilters(query)
    ? `${shown} of ${listState.totalCount} tickets match`
    : `${listState.totalCount} ${listState.totalCount === 1 ? "ticket" : "tickets"}`;

  const remaining = listState.othersTotal - listState.othersShown;
  loadMoreButton.hidden = remaining <= 0;
  loadMoreButton.querySelector("[data-button-text]").textContent = `Load more (${remaining} left)`;
}

/* ============================ QUERY & FILTERS ============================ */

function getQuery() {
  return {
    status: statusInput?.value ?? "",
    priority: priorityInput?.value ?? "",
    assignment: assignmentInput?.value ?? "",
    sort: sortInput?.value || DEFAULT_SORT,
    search: searchInput?.value.trim() ?? "",
  };
}

function hasActiveFilters(query) {
  return Boolean(query.status || query.priority || query.assignment || query.search);
}

function buildParams(query, page = 1) {
  const params = new URLSearchParams();
  if (query.status) params.set("status", query.status);
  if (query.priority) params.set("priority", query.priority);
  if (query.assignment) params.set("assignment", query.assignment);
  if (query.sort !== DEFAULT_SORT) params.set("sort", query.sort);
  if (query.search) params.set("search", query.search);
  if (page > 1) params.set("page", page);
  return params;
}

function syncUrl(query) {
  const queryString = buildParams(query).toString();
  // replaceState: typing a search shouldn't add a history entry per keystroke
  history.replaceState(null, "", queryString ? `${location.pathname}?${queryString}` : location.pathname);
}

function getDropdownLabel(input, value) {
  return input?.closest(".custom-dropdown")?.querySelector(`.dropdown-item[data-value="${CSS.escape(value)}"]`)?.dataset.label ?? value;
}

function setDropdownValue(input, value) {
  if (!input) return;
  const wrapper = input.closest(".custom-dropdown");
  const label = wrapper?.querySelector(".dropdown-label");
  const item = wrapper?.querySelector(`.dropdown-item[data-value="${CSS.escape(value)}"]`);

  input.value = value;
  if (label) {
    if (value && item) {
      label.textContent = item.dataset.label;
      label.classList.remove("text-foreground/80");
    } else {
      label.textContent = label.dataset.placeholder;
      label.classList.add("text-foreground/80");
    }
  }
  input.dispatchEvent(new Event("change", { bubbles: true }));
}

function clearQuery() {
  // Reset silently, then load once (instead of one request per control)
  [statusInput, priorityInput, assignmentInput].forEach((input) => {
    const label = input.closest(".custom-dropdown")?.querySelector(".dropdown-label");
    input.value = "";
    if (label) {
      label.textContent = label.dataset.placeholder;
      label.classList.add("text-foreground/80");
    }
  });
  searchInput.value = "";
  searchInput.focus();
  loadTickets();
}

function createFilterChip({ label, config, removeLabel, onRemove }) {
  const chip = el(
    "button",
    `group/chip inline-flex min-h-9 shrink-0 cursor-pointer items-center gap-1.5 rounded-full border py-1 pl-3 pr-1.5 font-sans text-sm font-semibold text-foreground outline-none transition-all duration-200 hover:shadow-sm focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2 active:scale-[0.97] ${config.chip}`,
  );
  chip.type = "button";
  chip.setAttribute("aria-label", removeLabel);
  chip.title = removeLabel;
  const x = el("span", "flex h-6 w-6 items-center justify-center rounded-full text-neutral-800 transition-colors group-hover/chip:bg-neutral-900/10 group-hover/chip:text-foreground");
  x.append(createIcon("x", "w-3.5 h-3.5"));
  chip.append(createIcon(config.icon, `w-4 h-4 ${config.iconColor}`), el("span", "max-w-48 truncate", label), x);

  chip.addEventListener("click", () => {
    const index = [...activeFilters.children].indexOf(chip);
    onRemove();
    // Keep keyboard focus near where it was once the chip is gone
    const remaining = activeFilters.querySelectorAll("button");
    (remaining[Math.min(index, remaining.length - 1)] ?? searchInput)?.focus();
  });
  return chip;
}

function renderFilterChips(query) {
  const chips = [];
  if (query.status) {
    const label = getDropdownLabel(statusInput, query.status);
    chips.push(createFilterChip({ label, config: TICKET_STATUS_CONFIG[query.status], removeLabel: `Remove status filter: ${label}`, onRemove: () => setDropdownValue(statusInput, "") }));
  }
  if (query.priority) {
    const label = getDropdownLabel(priorityInput, query.priority);
    chips.push(createFilterChip({ label: `${label} priority`, config: TICKET_PRIORITY_CONFIG[query.priority], removeLabel: `Remove priority filter: ${label}`, onRemove: () => setDropdownValue(priorityInput, "") }));
  }
  if (query.assignment) {
    const label = getDropdownLabel(assignmentInput, query.assignment);
    chips.push(createFilterChip({ label, config: ASSIGNMENT_CHIP_CONFIG[query.assignment], removeLabel: `Remove assignment filter: ${label}`, onRemove: () => setDropdownValue(assignmentInput, "") }));
  }
  if (query.search) {
    chips.push(createFilterChip({
      label: `“${query.search}”`,
      config: SEARCH_CHIP_CONFIG,
      removeLabel: `Remove search: ${query.search}`,
      onRemove: () => {
        searchInput.value = "";
        loadTickets();
      },
    }));
  }
  if (chips.length > 1) {
    const clearAll = cloneTemplate("tpl-button-clear-all");
    clearAll.addEventListener("click", clearQuery);
    chips.push(clearAll);
  }
  activeFilters.replaceChildren(...chips);
  renderLucideIcons(activeFilters);
}

/* ================================ LOADING ================================ */

let listController = null;

function setListsBusy(isBusy) {
  [assignedList, othersList].forEach((list) => {
    list.setAttribute("aria-busy", String(isBusy));
    list.classList.toggle("opacity-60", isBusy);
  });
}

async function loadTickets({ page = 1 } = {}) {
  const query = getQuery();
  if (page === 1) {
    syncUrl(query);
    renderFilterChips(query);
    // Sections that the assignment filter rules out are hidden, not shown empty
    assignedSection.hidden = query.assignment === "unassigned" || query.assignment === "others";
    othersSection.hidden = query.assignment === "me";
  }

  // A newer request makes the older one irrelevant
  listController?.abort();
  const controller = new AbortController();
  listController = controller;

  if (page === 1) setListsBusy(true);
  else setButtonLoading(loadMoreButton, true, "Loading…");

  try {
    const data = await getJson(`${LIST_URL}?${buildParams(query, page)}`, controller.signal);
    listState.totalCount = data.total_count;
    listState.othersTotal = data.others_total;
    listState.page = data.page;

    const newRows = data.others.map(createTicketRow);
    if (page === 1) {
      listState.assigned = data.assigned.length;
      assignedList.replaceChildren(...(data.assigned.length ? data.assigned.map(createTicketRow) : [assignedEmptyState(query)]));
      othersList.replaceChildren(...(newRows.length ? newRows : [othersEmptyState(query)]));
      listState.othersShown = newRows.length;
      renderLucideIcons(assignedList);
    } else {
      othersList.append(...newRows);
      listState.othersShown += newRows.length;
      // Keyboard users continue from the first newly loaded ticket
      newRows[0]?.querySelector("article")?.focus({ preventScroll: true });
    }
    renderLucideIcons(othersList);
    updateCounts(query);
  } catch (error) {
    if (error.name === "AbortError") return;
    console.error(error);
    window.showToast?.({ type: "error", title: "Couldn't load tickets", message: error.message });
  } finally {
    if (listController === controller) {
      setListsBusy(false);
      setButtonLoading(loadMoreButton, false);
      // After the button's own text is restored, so "N left" is current
      updateCounts(query);
    }
  }
}

/* ================================ ACTIONS ================================ */

function shortId(ticketId) {
  return `#${ticketId.slice(0, 8).toUpperCase()}`;
}

function removeRow(item, onRemoved) {
  const finish = () => {
    item.remove();
    onRemoved?.();
  };
  if (prefersReducedMotion.matches) return finish();
  item.classList.add("opacity-0", "scale-[0.98]");
  setTimeout(finish, 200);
}

async function assignTicket(ticket, button, item) {
  if (button.getAttribute("aria-busy") === "true") return;
  setButtonLoading(button, true, "Assigning…");

  try {
    const { response, data } = await postJson(ticketUrl(root.dataset.assignUrlTemplate, ticket.id));

    if (!response.ok) {
      window.showToast?.({ type: "error", title: "Couldn't assign ticket", message: data.error ?? `Request failed (${response.status})` });
      // Someone else may have taken it: show the current state
      if (response.status === 409) loadTickets();
      return;
    }

    window.showToast?.({ type: "success", title: "Assigned to you", message: `${shortId(ticket.id)} · ${ticket.title}` });

    // Move the row from "All other tickets" to "Assigned to you"
    removeRow(item, () => {
      listState.othersTotal -= 1;
      listState.othersShown -= 1;
      if (!othersList.querySelector("li[data-ticket-id]")) othersList.replaceChildren(othersEmptyState(getQuery()));

      if (!assignedSection.hidden) {
        assignedList.querySelector("[data-empty-state]")?.remove();
        const newItem = createTicketRow(data.ticket);
        assignedList.prepend(newItem);
        renderLucideIcons(newItem);
        listState.assigned += 1;
        const newRow = newItem.querySelector("article");
        newRow.scrollIntoView({ behavior: prefersReducedMotion.matches ? "auto" : "smooth", block: "nearest" });
        newRow.focus({ preventScroll: true });
        highlight(newRow);
      }
      updateCounts();
    });
    loadStats();
  } catch (error) {
    console.error(error);
    window.showToast?.({ type: "error", title: "Couldn't assign ticket", message: error.message });
  } finally {
    if (button.isConnected) setButtonLoading(button, false);
  }
}

let pendingDelete = null;

function openDeleteDialog(ticket, item) {
  pendingDelete = { ticket, item };
  document.getElementById("deleteTicketName").textContent = `${shortId(ticket.id)} “${ticket.title}”`;
  const replies = ticket.messages_count ?? 0;
  document.getElementById("deleteTicketReplies").textContent = `its ${replies} ${replies === 1 ? "reply" : "replies"}`;
  window.openModal("deleteTicketModal");
}

async function confirmDelete() {
  if (!pendingDelete || deleteConfirmButton.getAttribute("aria-busy") === "true") return;
  const { ticket, item } = pendingDelete;
  setButtonLoading(deleteConfirmButton, true, "Deleting…");

  try {
    const { response, data } = await postJson(ticketUrl(root.dataset.deleteUrlTemplate, ticket.id));
    if (!response.ok && response.status !== 404) {
      throw new Error(data.error ?? `Request failed (${response.status})`);
    }

    window.closeModal("deleteTicketModal");
    window.showToast?.({ type: "success", title: "Ticket deleted", message: `${shortId(ticket.id)} · ${ticket.title}` });

    const list = item.parentElement;
    const isAssigned = list === assignedList;
    // The trash button that opened the dialog is going away: move focus to the next ticket, or the section heading
    const nextFocus =
      item.nextElementSibling?.querySelector("article") ??
      item.previousElementSibling?.querySelector("article") ??
      document.getElementById(isAssigned ? "assignedTitle" : "othersTitle");

    removeRow(item, () => {
      if (isAssigned) listState.assigned -= 1;
      else {
        listState.othersTotal -= 1;
        listState.othersShown -= 1;
      }
      listState.totalCount -= 1;
      if (!list.querySelector("li[data-ticket-id]")) {
        list.replaceChildren(isAssigned ? assignedEmptyState(getQuery()) : othersEmptyState(getQuery()));
        renderLucideIcons(list);
      }
      updateCounts();
      nextFocus?.focus({ preventScroll: true });
    });
    loadStats();
    pendingDelete = null;
  } catch (error) {
    console.error(error);
    // The dialog stays open so the admin can retry or cancel
    window.showToast?.({ type: "error", title: "Couldn't delete ticket", message: error.message });
  } finally {
    setButtonLoading(deleteConfirmButton, false);
  }
}

/* ================================== INIT ================================== */

function debounce(callback, delay) {
  let timeoutId;
  return (...args) => {
    clearTimeout(timeoutId);
    timeoutId = setTimeout(() => callback(...args), delay);
  };
}

function init() {
  if (!root || !LIST_URL) return;

  // The dropdown component fires "change" on its hidden input
  [statusInput, priorityInput, assignmentInput, sortInput].forEach((input) =>
    input?.addEventListener("change", () => loadTickets()),
  );
  searchInput?.addEventListener("input", debounce(() => loadTickets(), SEARCH_DEBOUNCE_MS));
  loadMoreButton?.addEventListener("click", () => loadTickets({ page: listState.page + 1 }));
  refreshButton?.addEventListener("click", async () => {
    setButtonLoading(refreshButton, true, "Refreshing…");
    await Promise.all([loadStats(), loadTickets()]);
    setButtonLoading(refreshButton, false);
  });

  deleteConfirmButton?.addEventListener("click", confirmDelete);
  document.getElementById("deleteTicketModal")?.addEventListener("modal:close", () => {
    if (deleteConfirmButton.getAttribute("aria-busy") !== "true") pendingDelete = null;
  });

  // A one-time message left by another page (e.g. "Ticket deleted" from the ticket page)
  try {
    const flash = sessionStorage.getItem("dashboard-flash");
    if (flash) {
      sessionStorage.removeItem("dashboard-flash");
      window.showToast?.(JSON.parse(flash));
    }
  } catch {
    /* storage unavailable or bad JSON: nothing to show */
  }

  loadStats();
  loadTickets();
}

init();
