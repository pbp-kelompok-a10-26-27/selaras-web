// Ticket card, conversation and reply composer, shared by the user ticket page
// (helpdesk/ticket_detail.js) and the admin ticket page (dashboard/admin_ticket_detail.js).
import { createAttachmentGallery } from "./attachments.js";
import {
  TICKET_PRIORITY_CONFIG,
  TICKET_STATUS_CONFIG,
  cloneTemplate,
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

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)");

/* ================================= HELPERS ================================= */

const dateFormatter = new Intl.DateTimeFormat("id", { dateStyle: "medium" });
const timeFormatter = new Intl.DateTimeFormat("id", { timeStyle: "short" });

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

export async function readJsonResponse(response) {
  const contentType = response.headers.get("content-type") || "";
  if (!contentType.includes("application/json"))
    throw new Error("Server tidak merespons dengan benar. Sesimu mungkin sudah habis.");
  return response.json();
}

export function createDetailErrorState(message, onRetry) {
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
  retryButton.addEventListener("click", onRetry);

  error.append(text, retryButton);
  return error;
}

/* =============================== TICKET CARD =============================== */

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
    setButtonText(toggle, expanded ? "Lihat lebih banyak" : "Lihat lebih sedikit");
    toggleIcon.classList.toggle("rotate-180", !expanded);
  });

  // Only offer the toggle when the text is actually cut off (needs layout first)
  requestAnimationFrame(() => {
    toggle.hidden = body.scrollHeight <= body.clientHeight + 1;
  });

  box.append(body, toggle);
  return box;
}

export function createTicketDetailComponent(ticket, { animate = true } = {}) {
  const statusConfig =
    TICKET_STATUS_CONFIG[ticket.status] ?? TICKET_STATUS_CONFIG.open;
  const priorityConfig =
    TICKET_PRIORITY_CONFIG[ticket.priority] ?? TICKET_PRIORITY_CONFIG.normal;

  const card = el(
    "article",
    `${animate ? "slide-in-up " : ""}flex flex-col gap-6 rounded-3xl border border-neutral-400 bg-neutral-50 p-5 shadow-sm sm:p-8`,
  );
  card.id = "ticketCard";
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
    el("span", "text-xs text-neutral-800", "Dikirim pada"),
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
      ? createMetaElement("lock", "Ditutup", createTimeElement(ticket.closed_at))
      : createMetaElement("clock", "Terakhir diperbarui", createTimeElement(ticket.updated_at));

  people.append(
    createPersonElement(ticket.requester, {
      caption: "Pengirim",
      fallbackName: "Pengguna tidak dikenal",
    }),
    createPersonElement(ticket.assignee, {
      caption: "Koordinator",
      fallbackName: "Menunggu koordinator",
      captionNode: ticket.assignee ? document.createTextNode(ticket.assignee.role) : null,
    }),
    timeline,
  );

  const description = createCollapsibleText(
    ticket.description || "Tanpa deskripsi.",
    "rounded-2xl bg-neutral-300 p-4 sm:p-5",
  );

  card.append(header, people, description);
  const gallery = createAttachmentGallery(ticket.attachments);
  if (gallery) card.append(gallery);
  return card;
}

/* =============================== CONVERSATION =============================== */

function flash(node) {
  node.classList.add("ring-2", "ring-primary-500", "ring-offset-2");
  setTimeout(() => node.classList.remove("ring-2", "ring-primary-500", "ring-offset-2"), 1600);
}

// Jump to the message a reply quotes
function scrollToMessage(messageId) {
  const target = document.getElementById(`message-${messageId}`);
  if (!target) {
    window.showToast?.({ type: "info", title: "Pesan tidak tersedia", message: "Pesan aslinya mungkin sudah dihapus." });
    return;
  }
  target.scrollIntoView({ behavior: prefersReducedMotion.matches ? "auto" : "smooth", block: "center" });
  target.focus({ preventScroll: true });
  flash(target);
}

// The quote shown above a reply's text; clicking it goes to the original
function createReplyQuote(replyTo) {
  if (!replyTo) return null;

  const quote = el(
    "button",
    `mt-3 flex w-full cursor-pointer flex-col items-start gap-0.5 rounded-lg border-l-4 px-3 py-1.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-primary-500 sm:ml-12 sm:w-[calc(100%-3rem)] ${
      replyTo.is_admin_response
        ? "border-primary-500 bg-primary-100/70 hover:bg-primary-100"
        : "border-secondary-300 bg-neutral-300/80 hover:bg-neutral-300"
    }`,
  );
  quote.type = "button";
  quote.setAttribute("aria-label", `Membalas ${replyTo.author_name}: ${replyTo.excerpt}. Lihat pesan itu`);
  quote.title = "Lihat pesan asli";
  quote.append(
    el("span", "font-sans text-xs font-semibold text-secondary-800", replyTo.author_name),
    el("span", "line-clamp-2 break-words font-sans text-sm text-neutral-900", replyTo.excerpt),
  );
  quote.addEventListener("click", () => scrollToMessage(replyTo.id));
  return quote;
}

// Small "Reply" button: on hover/focus with a mouse, always visible on touch
// screens (no hover there). Only shown while the list has data-can-reply.
function createReplyButton(message) {
  const button = el(
    "button",
    "hidden min-h-8 shrink-0 cursor-pointer items-center gap-1.5 rounded-lg px-2 font-sans text-xs font-semibold text-secondary-700 outline-none transition-all duration-150 hover:bg-neutral-300 hover:text-secondary-900 focus-visible:opacity-100 focus-visible:ring-2 focus-visible:ring-primary-500 group-data-[can-reply]/conversation:inline-flex pointer-fine:opacity-0 pointer-fine:group-hover/message:opacity-100 pointer-fine:group-focus-within/message:opacity-100 pointer-fine:group-data-[replying]/message:opacity-100",
  );
  button.type = "button";
  button.dataset.replyButton = "";
  const author = message.is_own ? "pesanmu" : `pesan ${message.author?.name ?? "Pengguna terhapus"}`;
  button.setAttribute("aria-label", `Balas ${author}`);
  button.title = "Balas pesan ini";
  button.append(createIcon("corner-up-left", "w-3.5 h-3.5"), el("span", "", "Balas"));

  // The composer listens for this (initReplyComposer)
  button.addEventListener("click", () => {
    document.dispatchEvent(new CustomEvent("conversation:reply", { detail: { message } }));
  });
  return button;
}

function createMessageElement(message, { isNew = false } = {}) {
  const author = message.author ?? { name: "Pengguna terhapus", role: "" };

  // Support replies get a tinted card and accent so the back-and-forth is easy to scan
  const item = el(
    "li",
    `${isNew ? "slide-in-up ring-2 ring-primary-300 " : ""}group/message relative scroll-mt-24 overflow-hidden rounded-2xl border p-4 outline-none transition-shadow duration-700 data-[replying]:ring-2 data-[replying]:ring-primary-300 sm:p-5 ${
      message.is_admin_response
        ? "border-primary-300/70 bg-primary-50"
        : "border-neutral-400 bg-neutral-50"
    }`,
  );
  item.id = `message-${message.id}`;
  item.tabIndex = -1;

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
        "Tim bantuan",
      ),
    );
  }
  if (message.is_own) {
    nameRow.append(
      el(
        "span",
        "rounded-full border border-neutral-500 bg-neutral-300 px-2 py-0.5 font-sans text-[0.6875rem] font-semibold text-neutral-900",
        "Kamu",
      ),
    );
  }

  who.append(createAvatarElement(message.author, "h-9 w-9 text-xs"), nameRow);

  const side = el("div", "ml-12 flex items-center gap-2 sm:ml-0");
  side.append(
    createDateTimeElement(message.created_at, "font-sans text-xs text-neutral-800"),
    createReplyButton(message),
  );
  header.append(who, side);

  // Body lines up with the name on wider screens, full width on phones
  const body = el(
    "p",
    "mt-3 whitespace-pre-line break-words font-sans text-b3 text-foreground sm:pl-12",
    message.message,
  );

  const quote = createReplyQuote(message.reply_to);
  item.append(header, ...(quote ? [quote] : []), body);

  if (isNew) {
    // Briefly highlight the reply that was just sent, then fade the ring out
    setTimeout(() => item.classList.remove("ring-2", "ring-primary-300"), 1600);
  }
  return item;
}

function createMessagesEmptyState(text) {
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
    el("p", "font-sans text-sm font-semibold text-foreground", "Belum ada balasan"),
    el("p", "max-w-sm font-sans text-sm text-neutral-800", text),
  );
  return empty;
}

function formatMessageCount(count) {
  return `${count} ${count === 1 ? "message" : "messages"}`;
}

export function createTicketMessagesComponent(
  messages,
  {
    canReply = false,
    emptyText = "Tim bantuan akan membalas di sini. Sambil menunggu, kamu bisa menambahkan detail di bawah.",
  } = {},
) {
  const section = el("section", "flex flex-col gap-4");
  section.setAttribute("aria-labelledby", "conversationTitle");

  const header = el("div", "flex items-center justify-between gap-3");
  const title = el("h2", "flex items-center gap-2 font-sans text-lg font-semibold text-foreground");
  title.id = "conversationTitle";
  title.append(createIcon("messages-square", "w-5 h-5 text-secondary-500"), el("span", "", "Riwayat percakapan"));

  const count = el(
    "span",
    "font-sans text-xs font-semibold uppercase tracking-wider text-neutral-800",
    formatMessageCount(messages.length),
  );
  count.id = "conversationCount";
  header.append(title, count);

  const list = el("ol", "group/conversation flex flex-col gap-3");
  list.id = "conversationList";
  list.toggleAttribute("data-can-reply", canReply);
  list.append(
    ...(messages.length
      ? messages.map((message) => createMessageElement(message))
      : [createMessagesEmptyState(emptyText)]),
  );

  section.append(header, list);
  return section;
}

// Shows or hides every message's Reply button at once (e.g. after closing a ticket)
export function setConversationReplyable(canReply) {
  document.getElementById("conversationList")?.toggleAttribute("data-can-reply", canReply);
}

export function appendMessage(message) {
  const list = document.getElementById("conversationList");
  if (!list) return;

  list.querySelector("[data-empty-state]")?.remove();
  const item = createMessageElement(message, { isNew: true });
  list.append(item);
  renderLucideIcons(item);

  const count = document.getElementById("conversationCount");
  if (count) count.textContent = formatMessageCount(list.querySelectorAll("li[id^='message-']").length);

  item.scrollIntoView({ behavior: prefersReducedMotion.matches ? "auto" : "smooth", block: "nearest" });
}

/* ============================== REPLY COMPOSER ============================== */

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

/**
 * Wires up the reply form from templates/helpdesk/_reply_composer.html.
 * Returns { setReplyTo, clearReplyTo, setClosed } so a page can drive it, or null.
 */
export function initReplyComposer({ onSent } = {}) {
  const form = document.getElementById("ticketReplyForm");
  const textarea = document.getElementById("ticketReplyMessage");
  const count = document.getElementById("ticketReplyCount");
  const submit = document.getElementById("ticketReplySubmit");
  const replyToInput = document.getElementById("ticketReplyTo");
  const preview = document.getElementById("ticketReplyPreview");
  const closedNotice = document.getElementById("ticketClosedNotice");
  if (!form || !textarea || !submit) return null;

  const maxLength = Number(textarea.maxLength) || 5000;

  function autoResize() {
    textarea.style.height = "auto";
    textarea.style.height = `${textarea.scrollHeight}px`;
  }

  function updateState() {
    const length = textarea.value.length;
    count.textContent = `${length} / ${maxLength}`;
    // Warn as the limit gets close, instead of only after hitting it
    count.classList.toggle("text-red-100", length > maxLength * 0.9);
    count.classList.toggle("font-semibold", length > maxLength * 0.9);
    submit.disabled = textarea.value.trim() === "";
  }

  function setSending(isSending) {
    submit.disabled = isSending || textarea.value.trim() === "";
    textarea.readOnly = isSending;
    setButtonLoading(submit, isSending, "Mengirim…");
  }

  /* ---- Reply to a specific message ---- */

  function markReplying(messageId) {
    document.querySelectorAll("#conversationList [data-replying]").forEach((li) => li.removeAttribute("data-replying"));
    if (messageId) document.getElementById(`message-${messageId}`)?.setAttribute("data-replying", "");
  }

  function setReplyTo(message) {
    replyToInput.value = message.id;
    preview.querySelector("[data-reply-author]").textContent = message.is_own ? "yourself" : message.author?.name ?? "Pengguna terhapus";
    preview.querySelector("[data-reply-excerpt]").textContent = message.message;
    preview.hidden = false;
    markReplying(message.id);

    form.scrollIntoView({ behavior: prefersReducedMotion.matches ? "auto" : "smooth", block: "nearest" });
    textarea.focus({ preventScroll: true });
  }

  function clearReplyTo({ focus = false } = {}) {
    replyToInput.value = "";
    preview.hidden = true;
    markReplying(null);
    if (focus) textarea.focus();
  }

  document.addEventListener("conversation:reply", (event) => setReplyTo(event.detail.message));
  preview.querySelector("[data-reply-cancel]").addEventListener("click", () => clearReplyTo({ focus: true }));

  /* ---- Sending ---- */

  async function submitReply(event) {
    // Without JS the form posts normally; with JS we stay on the page
    event.preventDefault();
    if (submit.disabled) return;

    setSending(true);
    try {
      const response = await fetch(form.dataset.apiUrl, {
        method: "POST",
        headers: { Accept: "application/json" },
        // FormData includes the csrfmiddlewaretoken from {% csrf_token %} and reply_to
        body: new FormData(form),
      });

      const data = await readJsonResponse(response);
      if (!response.ok) throw new Error(data.error ?? `Balasan gagal dikirim (${response.status})`);

      appendMessage(data.message);
      textarea.value = "";
      draftStorage.set(form.dataset.draftKey, "");
      clearReplyTo();
      autoResize();
      onSent?.(data.message);

      window.showToast?.({
        type: "success",
        title: "Balasan terkirim",
        message: "Pesanmu sudah masuk ke percakapan.",
        duration: 2500,
      });
    } catch (error) {
      console.error(error);
      // The text (and the quoted message) are kept, so nothing is lost
      window.showToast?.({ type: "error", title: "Balasan gagal dikirim", message: error.message });
    } finally {
      setSending(false);
      updateState();
      textarea.focus();
    }
  }

  textarea.value = draftStorage.get(form.dataset.draftKey);
  autoResize();
  updateState();

  textarea.addEventListener("input", () => {
    autoResize();
    updateState();
    draftStorage.set(form.dataset.draftKey, textarea.value);
  });

  textarea.addEventListener("keydown", (event) => {
    // Ctrl+Enter (Cmd+Enter on Mac) sends; plain Enter still adds a new line
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      form.requestSubmit();
    }
    // Escape drops the quoted message first (like WhatsApp)
    if (event.key === "Escape" && replyToInput.value) {
      event.preventDefault();
      event.stopPropagation();
      clearReplyTo({ focus: true });
    }
  });

  form.addEventListener("submit", submitReply);

  // Closing a ticket swaps the form for the "closed" notice (and back on reopen)
  function setClosed(isClosed) {
    form.hidden = isClosed;
    if (closedNotice) closedNotice.hidden = !isClosed;
    if (isClosed) clearReplyTo();
  }

  return { setReplyTo, clearReplyTo, setClosed };
}
