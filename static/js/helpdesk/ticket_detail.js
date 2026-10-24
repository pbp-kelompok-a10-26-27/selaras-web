import "./../components/toast/toast.js";
import {
  TICKET_PRIORITY_CONFIG,
  TICKET_STATUS_CONFIG,
  cloneTemplate,
  cloneTemplateContent,
  createAvatarElement,
  createChipElement,
  createIcon,
  createPersonElement,
  createTicketIdElement,
  createTimeElement,
  el,
  formatRelativeTime,
  renderLucideIcons,
  setButtonLoading,
  setButtonText,
} from "./shared.js";

const ticketContainerId = document.getElementById("ticketCardSection");
const TICKET_DETAIL_API_URL = ticketContainerId?.dataset.detailUrl;

const replyForm = document.getElementById("ticketReplyForm");
const replyTextarea = document.getElementById("ticketReplyMessage");
const replyCount = document.getElementById("ticketReplyCount");
const replySubmit = document.getElementById("ticketReplySubmit");

const REPLY_MAX_LENGTH = Number(replyTextarea?.maxLength) || 5000;

const dateFormatter = new Intl.DateTimeFormat(undefined, { dateStyle: "medium" });
const timeFormatter = new Intl.DateTimeFormat(undefined, { timeStyle: "short" });

// "May 12, 2024 · 9:30 AM", like the design
function formatDateTime(date) {
  return `${dateFormatter.format(date)} · ${timeFormatter.format(date)}`;
}

// Absolute date shown, relative time on hover: exact for records, friendly on demand
function createDateTimeElement(isoString, className = "") {
  const time = el("time", className);
  if (!isoString) {
    time.textContent = "—";
    return time;
  }

  const date = new Date(isoString);
  time.dateTime = isoString;
  time.title = formatRelativeTime(date);
  time.textContent = formatDateTime(date);
  return time;
}

// Like createPersonElement, but with an icon instead of an avatar
function createMetaElement(icon, caption, valueNode) {
  const meta = el("div", "flex min-w-0 flex-1 items-center gap-3");
  const iconBox = el(
    "span",
    "flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-neutral-300 text-neutral-900",
  );
  iconBox.append(createIcon(icon, "w-4 h-4"));

  const text = el("div", "flex min-w-0 flex-col");
  const value = el("span", "truncate font-sans text-sm font-semibold text-foreground");
  value.append(valueNode);
  text.append(
    el(
      "span",
      "font-sans text-[0.6875rem] font-semibold uppercase tracking-wider text-neutral-800",
      caption,
    ),
    value,
  );

  meta.append(iconBox, text);
  return meta;
}

// Long descriptions start collapsed, with a toggle to read the rest
function createCollapsibleText(text, boxClassName) {
  const box = el("div", boxClassName);
  const body = el(
    "p",
    "line-clamp-6 whitespace-pre-line break-words font-sans text-b3 text-foreground",
    text,
  );
  body.id = "ticketDescriptionText";

  const toggle = cloneTemplate("tpl-button-show-more");
  // The hidden attribute, not a class: the button already has `inline-flex`
  toggle.hidden = true;
  toggle.setAttribute("aria-controls", body.id);
  toggle.setAttribute("aria-expanded", "false");
  const toggleIcon = toggle.querySelector("[data-button-icon-right]");

  toggle.addEventListener("click", () => {
    const expanded = toggle.getAttribute("aria-expanded") === "true";
    toggle.setAttribute("aria-expanded", String(!expanded));
    body.classList.toggle("line-clamp-6", expanded);
    setButtonText(toggle, expanded ? "Show more" : "Show less");
    toggleIcon.classList.toggle("rotate-180", !expanded);
  });

  // Only offer the toggle when the text is actually cut off (needs layout first)
  requestAnimationFrame(() => {
    toggle.hidden = body.scrollHeight <= body.clientHeight + 1;
  });

  box.append(body, toggle);
  return box;
}

function createTicketDetailComponent(ticket) {
  const statusConfig =
    TICKET_STATUS_CONFIG[ticket.status] ?? TICKET_STATUS_CONFIG.open;
  const priorityConfig =
    TICKET_PRIORITY_CONFIG[ticket.priority] ?? TICKET_PRIORITY_CONFIG.normal;

  const card = el(
    "article",
    "slide-in-up flex flex-col gap-6 rounded-3xl border border-neutral-400 bg-neutral-50 p-5 shadow-sm sm:p-8",
  );
  card.setAttribute("aria-labelledby", "ticketTitle");

  // Header: chips + title on the left, submitted date on the right
  const header = el(
    "header",
    "flex flex-col gap-4 md:flex-row md:items-start md:justify-between md:gap-8",
  );

  const headingGroup = el("div", "flex min-w-0 flex-col gap-3");
  const chips = el("div", "flex flex-wrap items-center gap-2");
  chips.append(
    createTicketIdElement(ticket.id),
    createChipElement(`${ticket.priority_label} priority`, priorityConfig),
    createChipElement(ticket.status_label, statusConfig),
  );

  const title = el(
    "h1",
    "break-words font-sans text-h4 leading-tight text-foreground sm:text-h3",
    ticket.title,
  );
  title.id = "ticketTitle";
  headingGroup.append(chips, title);

  const submitted = el(
    "div",
    "flex shrink-0 flex-col gap-0.5 font-sans md:items-end md:text-right",
  );
  submitted.append(
    el("span", "text-xs text-neutral-800", "Submitted on"),
    createDateTimeElement(ticket.created_at, "text-sm font-semibold text-foreground"),
  );
  header.append(headingGroup, submitted);

  // People + timeline. The design's "Target resolution SLA" has no backing
  // field yet, so the third slot shows when the ticket last changed instead.
  const people = el(
    "div",
    "grid grid-cols-1 gap-4 border-y border-neutral-400 py-5 sm:grid-cols-2 lg:grid-cols-3",
  );
  const timeline =
    ticket.status === "closed" && ticket.closed_at
      ? createMetaElement("lock", "Closed", createTimeElement(ticket.closed_at))
      : createMetaElement("clock", "Last updated", createTimeElement(ticket.updated_at));

  people.append(
    createPersonElement(ticket.requester, {
      caption: "Requester",
      fallbackName: "Unknown user",
    }),
    createPersonElement(ticket.assignee, {
      caption: "Assigned coordinator",
      fallbackName: "Awaiting assignment",
      captionNode: ticket.assignee ? document.createTextNode(ticket.assignee.role) : null,
    }),
    timeline,
  );

  const description = createCollapsibleText(
    ticket.description || "No description provided.",
    "rounded-2xl bg-neutral-300 p-4 sm:p-5",
  );

  card.append(header, people, description);
  return card;
}

function createMessageElement(message, { isNew = false } = {}) {
  const author = message.author ?? { name: "Deleted user", role: "" };

  // Support replies get a tinted card and accent so the back-and-forth is easy to scan
  const item = el(
    "li",
    `${isNew ? "slide-in-up ring-2 ring-primary-300 " : ""}relative overflow-hidden rounded-2xl border p-4 transition-shadow duration-700 sm:p-5 ${
      message.is_admin_response
        ? "border-primary-300/70 bg-primary-50"
        : "border-neutral-400 bg-neutral-50"
    }`,
  );
  item.id = `message-${message.id}`;

  if (message.is_admin_response) {
    const accent = el("span", "absolute inset-y-0 left-0 w-1 bg-primary-500");
    accent.setAttribute("aria-hidden", "true");
    item.append(accent);
  }

  const header = el("div", "flex flex-wrap items-center gap-x-3 gap-y-1");
  const who = el("div", "flex min-w-0 flex-1 items-center gap-3");
  const nameRow = el("div", "flex min-w-0 flex-wrap items-center gap-2");
  nameRow.append(
    el("span", "truncate font-sans text-sm font-semibold text-foreground", author.name),
  );

  if (message.is_admin_response) {
    nameRow.append(
      el(
        "span",
        "rounded-full border border-primary-500/50 bg-primary-200 px-2 py-0.5 font-sans text-[0.6875rem] font-semibold text-primary-900",
        "Support team",
      ),
    );
  }
  if (message.is_own) {
    nameRow.append(
      el(
        "span",
        "rounded-full border border-neutral-500 bg-neutral-300 px-2 py-0.5 font-sans text-[0.6875rem] font-semibold text-neutral-900",
        "You",
      ),
    );
  }

  who.append(createAvatarElement(message.author, "h-9 w-9 text-xs"), nameRow);
  header.append(
    who,
    createDateTimeElement(
      message.created_at,
      "ml-12 font-sans text-xs text-neutral-800 sm:ml-0",
    ),
  );

  // Body lines up with the name on wider screens, full width on phones
  const body = el(
    "p",
    "mt-3 whitespace-pre-line break-words font-sans text-b3 text-foreground sm:pl-12",
    message.message,
  );

  item.append(header, body);

  if (isNew) {
    // Briefly highlight the reply that was just sent, then fade the ring out
    setTimeout(() => item.classList.remove("ring-2", "ring-primary-300"), 1600);
  }
  return item;
}

function createMessagesEmptyState() {
  const empty = el(
    "li",
    "flex flex-col items-center gap-2 rounded-2xl border-2 border-dashed border-neutral-500 px-6 py-10 text-center",
  );
  empty.dataset.emptyState = "";
  const iconBox = el(
    "span",
    "flex h-12 w-12 items-center justify-center rounded-2xl bg-primary-100 text-primary-700",
  );
  iconBox.append(createIcon("message-square-dashed", "w-6 h-6"));
  empty.append(
    iconBox,
    el("p", "font-sans text-sm font-semibold text-foreground", "No replies yet"),
    el(
      "p",
      "max-w-sm font-sans text-sm text-neutral-800",
      "Our support team will respond here. You can add more details below in the meantime.",
    ),
  );
  return empty;
}

function formatMessageCount(count) {
  return `${count} ${count === 1 ? "message" : "messages"}`;
}

function createTicketMessagesComponent(messages) {
  const section = el("section", "flex flex-col gap-4");
  section.setAttribute("aria-labelledby", "conversationTitle");

  const header = el("div", "flex items-center justify-between gap-3");
  const title = el("h2", "flex items-center gap-2 font-sans text-lg font-semibold text-foreground");
  title.id = "conversationTitle";
  title.append(createIcon("messages-square", "w-5 h-5 text-secondary-500"), el("span", "", "Conversation history"));

  const count = el(
    "span",
    "font-sans text-xs font-semibold uppercase tracking-wider text-neutral-800",
    formatMessageCount(messages.length),
  );
  count.id = "conversationCount";
  header.append(title, count);

  const list = el("ol", "flex flex-col gap-3");
  list.id = "conversationList";
  list.append(
    ...(messages.length
      ? messages.map((message) => createMessageElement(message))
      : [createMessagesEmptyState()]),
  );

  section.append(header, list);
  return section;
}

function appendMessage(message) {
  const list = document.getElementById("conversationList");
  if (!list) return;

  list.querySelector("[data-empty-state]")?.remove();
  const item = createMessageElement(message, { isNew: true });
  list.append(item);
  renderLucideIcons(item);

  const count = document.getElementById("conversationCount");
  if (count) count.textContent = formatMessageCount(list.children.length);

  item.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// Built from the skeleton component (<template id="tpl-detail-skeleton"> in ticket_detail.html)
function createTicketDetailSkeleton() {
  return cloneTemplateContent("tpl-detail-skeleton");
}

function createTicketDetailErrorState(message) {
  const error = el(
    "div",
    "flex flex-col items-start gap-3 rounded-3xl border border-red-100/40 bg-red-100/5 p-5 sm:flex-row sm:items-center",
  );
  const text = el("div", "flex flex-1 items-center gap-3");
  text.append(
    createIcon("triangle-alert", "w-5 h-5 shrink-0 text-red-100"),
    el("p", "font-sans text-sm text-foreground", message),
  );

  const retryButton = cloneTemplate("tpl-button-retry");
  retryButton.addEventListener("click", loadTicketDetail);

  error.append(text, retryButton);
  return error;
}

async function readJsonResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json"))
    throw new Error("Server did not return JSON. Your session may be expired");
  return response.json();
}

async function loadTicketDetail() {
  if (!ticketContainerId || !TICKET_DETAIL_API_URL) return;

  ticketContainerId.setAttribute("aria-busy", "true");
  ticketContainerId.replaceChildren(createTicketDetailSkeleton());

  try {
    const response = await fetch(TICKET_DETAIL_API_URL, {
      headers: { Accept: "application/json" },
    });

    const data = await readJsonResponse(response);
    if (!response.ok)
      throw new Error(data.error ?? `Failed to fetch ticket details (${response.status})`);

    ticketContainerId.replaceChildren(
      createTicketDetailComponent(data.ticket),
      createTicketMessagesComponent(data.messages ?? []),
    );
  } catch (error) {
    console.error("Error loading ticket details:", error);
    ticketContainerId.replaceChildren(
      createTicketDetailErrorState("We couldn't load this ticket."),
    );
  } finally {
    ticketContainerId.removeAttribute("aria-busy");
    renderLucideIcons(ticketContainerId);
  }
}

/* ============================ REPLY COMPOSER ============================ */

// Drafts survive an accidental refresh or navigation. Storage can be
// unavailable (private mode), so every access is guarded.
const draftStorage = {
  get(key) {
    try {
      return localStorage.getItem(key) ?? "";
    } catch {
      return "";
    }
  },
  set(key, value) {
    try {
      if (value) localStorage.setItem(key, value);
      else localStorage.removeItem(key);
    } catch {
      /* ignore */
    }
  },
};

function autoResizeTextarea() {
  replyTextarea.style.height = "auto";
  replyTextarea.style.height = `${replyTextarea.scrollHeight}px`;
}

function updateReplyState() {
  const length = replyTextarea.value.length;
  replyCount.textContent = `${length} / ${REPLY_MAX_LENGTH}`;
  // Warn as the limit gets close, instead of only after hitting it
  replyCount.classList.toggle("text-red-100", length > REPLY_MAX_LENGTH * 0.9);
  replyCount.classList.toggle("font-semibold", length > REPLY_MAX_LENGTH * 0.9);
  replySubmit.disabled = replyTextarea.value.trim() === "";
}

function setReplySending(isSending) {
  replySubmit.disabled = isSending || replyTextarea.value.trim() === "";
  replyTextarea.readOnly = isSending;
  setButtonLoading(replySubmit, isSending, "Sending…");
}

async function submitReply(event) {
  // Without JS the form posts normally; with JS we stay on the page
  event.preventDefault();
  if (replySubmit.disabled) return;

  setReplySending(true);

  try {
    const response = await fetch(replyForm.dataset.apiUrl, {
      method: "POST",
      headers: { Accept: "application/json" },
      // FormData includes the csrfmiddlewaretoken from {% csrf_token %}
      body: new FormData(replyForm),
    });

    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error ?? `Failed to send reply (${response.status})`);

    appendMessage(data.message);
    replyTextarea.value = "";
    draftStorage.set(replyForm.dataset.draftKey, "");
    autoResizeTextarea();

    window.showToast?.({
      type: "success",
      title: "Reply sent",
      message: "Your message was added to the conversation.",
      duration: 2500,
    });
  } catch (error) {
    console.error(error);
    // The text is kept, so nothing the user wrote is lost
    window.showToast?.({
      type: "error",
      title: "Couldn't send reply",
      message: error.message,
    });
  } finally {
    setReplySending(false);
    updateReplyState();
    replyTextarea.focus();
  }
}

function initReplyComposer() {
  if (!replyForm || !replyTextarea || !replySubmit) return;

  replyTextarea.value = draftStorage.get(replyForm.dataset.draftKey);
  autoResizeTextarea();
  updateReplyState();

  replyTextarea.addEventListener("input", () => {
    autoResizeTextarea();
    updateReplyState();
    draftStorage.set(replyForm.dataset.draftKey, replyTextarea.value);
  });

  // Ctrl+Enter (Cmd+Enter on Mac) sends; plain Enter still adds a new line
  replyTextarea.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      replyForm.requestSubmit();
    }
  });

  replyForm.addEventListener("submit", submitReply);
}

loadTicketDetail();
initReplyComposer();
