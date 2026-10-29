import "./../components/toast/toast.js";
import { cloneTemplateContent, renderLucideIcons, setButtonLoading } from "../helpdesk/shared.js";
import {
  createDetailErrorState,
  createTicketDetailComponent,
  createTicketMessagesComponent,
  initReplyComposer,
  readJsonResponse,
  setConversationReplyable,
} from "../helpdesk/conversation.js";

const root = document.getElementById("adminTicketDetail");
const csrfToken = document.getElementById("dashboardCsrfToken")?.value ?? "";
const container = document.getElementById("ticketCardSection");
const composerSection = document.getElementById("adminComposer");
const statusButtons = [...document.querySelectorAll("[data-status-action]")];
const assignButton = document.getElementById("adminAssignButton");
const deleteButton = document.getElementById("adminDeleteButton");
const notice = document.getElementById("adminPermissionNotice");

const ACTIVE_STATUSES = ["open", "in_progress"];
const FLASH_KEY = "dashboard-flash";

let ticket = null;
let composer = null;

/* ================================ REQUESTS ================================ */

async function post(url, body) {
  const response = await fetch(url, {
    method: "POST",
    headers: { Accept: "application/json", "X-CSRFToken": csrfToken },
    body,
  });
  const data = await readJsonResponse(response);
  if (!response.ok) throw new Error(data.error ?? `Permintaan gagal (${response.status})`);
  return data;
}

/* ============================== PERMISSIONS ============================== */

const NOTICES = {
  owner: { icon: "shield-check", tone: "bg-primary-100 text-primary-900", text: "Kamu koordinator tiket ini: kamu bisa membalas dan mengubah statusnya." },
  unassigned: { icon: "inbox", tone: "bg-yellow-100/50 text-secondary-900", text: "Belum ada koordinator. Ambil tiket ini untuk membalas dan mengubah statusnya." },
  others: { icon: "eye", tone: "bg-neutral-300 text-neutral-900", text: "" },
};

// Keeps everything that depends on "who can do what" in step with the ticket
function applyPermissions() {
  const isOwner = ticket.can_update_status;

  statusButtons.forEach((button) => {
    button.disabled = !isOwner;
    button.setAttribute("aria-pressed", String(button.dataset.statusAction === ticket.status));
    button.title = isOwner ? `Ubah status jadi ${button.dataset.statusLabel}` : "Hanya koordinator tiket yang bisa mengubah status";
  });

  assignButton.hidden = !ticket.can_assign_to_me;
  composerSection.hidden = !isOwner;
  composer?.setClosed(ticket.status === "closed");
  setConversationReplyable(ticket.can_reply);

  const kind = isOwner ? "owner" : ticket.assignee ? "others" : "unassigned";
  const { icon, tone, text } = NOTICES[kind];
  notice.className = `flex items-start gap-2 rounded-xl px-3 py-2 font-sans text-sm ${tone}`;
  const iconSlot = notice.querySelector("[data-notice-icon]");
  iconSlot.innerHTML = `<i data-lucide="${icon}" class="w-4 h-4" aria-hidden="true"></i>`;
  notice.querySelector("[data-notice-text]").textContent =
    kind === "others" ? `Hanya lihat. Tiket ini ditangani ${ticket.assignee.name}, jadi cuma dia yang bisa membalas atau mengubah status.` : text;
  renderLucideIcons(notice);
}

// The sidebar's Helpdesk badge counts the admin's open / in-progress tickets
function adjustSidebarBadge(delta) {
  const countEl = document.querySelector('[data-sidebar-key="helpdesk"] [data-sidebar-badge-count]');
  if (!countEl || !delta) return;
  const next = Math.max(0, Number(countEl.textContent) + delta);
  window.setSidebarBadge?.("helpdesk", next, `${next} tiket aktif ditugaskan ke kamu`);
}

function isActiveForMe(t) {
  return t.is_assigned_to_me && ACTIVE_STATUSES.includes(t.status);
}

// Re-render the ticket card in place (no entrance animation) after a change
function refreshCard() {
  const card = createTicketDetailComponent(ticket, { animate: false });
  document.getElementById("ticketCard")?.replaceWith(card);
  renderLucideIcons(card);
}

/* ================================ LOADING ================================ */

async function loadDetail() {
  container.setAttribute("aria-busy", "true");
  container.replaceChildren(cloneTemplateContent("tpl-detail-skeleton"));

  try {
    const response = await fetch(root.dataset.detailUrl, { headers: { Accept: "application/json" } });
    const data = await readJsonResponse(response);
    if (!response.ok) throw new Error(data.error ?? `Tiket gagal dimuat (${response.status})`);

    ticket = data.ticket;
    container.replaceChildren(
      createTicketDetailComponent(ticket),
      createTicketMessagesComponent(data.messages ?? [], {
        canReply: ticket.can_reply,
        emptyText: ticket.can_reply
          ? "Belum ada pesan. Mulai percakapan di bawah."
          : "Belum ada pesan.",
      }),
    );
    applyPermissions();
  } catch (error) {
    console.error(error);
    container.replaceChildren(createDetailErrorState("Tiket ini gagal dimuat.", loadDetail));
  } finally {
    container.removeAttribute("aria-busy");
    renderLucideIcons(container);
  }
}

/* ================================ ACTIONS ================================ */

async function setStatus(button) {
  const status = button.dataset.statusAction;
  if (!ticket || status === ticket.status || button.getAttribute("aria-busy") === "true") return;

  const wasActiveForMe = isActiveForMe(ticket);
  statusButtons.forEach((b) => b.setAttribute("aria-busy", "true"));

  try {
    const body = new FormData();
    body.append("status", status);
    const data = await post(root.dataset.updateUrl, body);

    ticket = data.ticket;
    refreshCard();
    applyPermissions();
    adjustSidebarBadge(Number(isActiveForMe(ticket)) - Number(wasActiveForMe));

    window.showToast?.({
      type: "success",
      title: `Status: ${button.dataset.statusLabel}`,
      message: status === "closed"
        ? "Percakapan ditutup untuk kedua pihak."
        : status === "resolved"
          ? "Pengirim masih bisa membalas kalau masalahnya belum beres."
          : "Tiket kembali diproses.",
    });
    button.focus();
  } catch (error) {
    console.error(error);
    window.showToast?.({ type: "error", title: "Status gagal diubah", message: error.message });
  } finally {
    statusButtons.forEach((b) => b.removeAttribute("aria-busy"));
  }
}

let pendingCloseButton = null;

function onStatusClick(event) {
  const button = event.currentTarget;
  if (button.disabled || button.dataset.statusAction === ticket?.status) return;

  // Closing ends the conversation for both sides, so confirm it first
  if (button.dataset.statusAction === "closed") {
    pendingCloseButton = button;
    window.openModal("closeTicketModal");
    return;
  }
  setStatus(button);
}

async function confirmClose() {
  if (!pendingCloseButton) return;
  const button = pendingCloseButton;
  pendingCloseButton = null;
  window.closeModal("closeTicketModal");
  await setStatus(button);
}

async function assignToMe() {
  if (assignButton.getAttribute("aria-busy") === "true") return;
  setButtonLoading(assignButton, true, "Mengambil tiket…");

  try {
    await post(root.dataset.assignUrl);
    window.showToast?.({ type: "success", title: "Tiket jadi milikmu", message: "Sekarang kamu bisa membalas dan mengubah statusnya." });
    // Permissions change across the page; reload the ticket with the new ones
    await loadDetail();
    adjustSidebarBadge(Number(isActiveForMe(ticket)));
    document.getElementById("ticketReplyMessage")?.focus();
  } catch (error) {
    console.error(error);
    window.showToast?.({ type: "error", title: "Tiket gagal diambil", message: error.message });
    loadDetail();
  } finally {
    setButtonLoading(assignButton, false);
  }
}

async function confirmDelete() {
  const confirmButton = document.getElementById("deleteTicketConfirm");
  if (confirmButton.getAttribute("aria-busy") === "true") return;
  setButtonLoading(confirmButton, true, "Menghapus…");

  try {
    await post(root.dataset.deleteUrl);
    // Shown by admin_tickets.js on the list page we're going back to
    try {
      sessionStorage.setItem(FLASH_KEY, JSON.stringify({ type: "success", title: "Tiket dihapus", message: ticket?.title ?? "" }));
    } catch {
      /* storage unavailable: the list still loads, just without the toast */
    }
    window.location.href = root.dataset.listUrl;
  } catch (error) {
    console.error(error);
    window.showToast?.({ type: "error", title: "Tiket gagal dihapus", message: error.message });
    setButtonLoading(confirmButton, false);
  }
}

/* ================================== INIT ================================== */

function init() {
  if (!root) return;

  statusButtons.forEach((button) => button.addEventListener("click", onStatusClick));
  document.getElementById("closeTicketConfirm")?.addEventListener("click", confirmClose);
  document.getElementById("closeTicketModal")?.addEventListener("modal:close", () => (pendingCloseButton = null));
  assignButton?.addEventListener("click", assignToMe);
  deleteButton?.addEventListener("click", () => window.openModal("deleteTicketModal"));
  document.getElementById("deleteTicketConfirm")?.addEventListener("click", confirmDelete);

  composer = initReplyComposer();
  loadDetail();
}

init();
