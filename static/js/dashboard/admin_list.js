// Halaman daftar admin: filter dropdown langsung terkirim, modal konfirmasi bersama, toast.
import { showMessagesAsToasts } from "../accounts/shared.js";

showMessagesAsToasts();

// The dropdown component fires a bubbling "change" on its hidden input
document.querySelectorAll("form[data-autosubmit]").forEach((form) => {
  form.addEventListener("change", (event) => {
    if (event.target.type === "hidden") form.requestSubmit();
  });
});

const modalTitle = document.getElementById("adminConfirmModal-title");
const form = document.getElementById("adminConfirmForm");
const body = document.getElementById("adminConfirmBody");
const fields = document.getElementById("adminConfirmFields");
const noteWrap = document.getElementById("adminConfirmNoteWrap");
const note = document.getElementById("adminConfirmNote");
const noteLabel = document.getElementById("adminConfirmNoteLabel");
const noteHint = document.getElementById("adminConfirmNoteHint");
const dangerBtn = document.getElementById("adminConfirmDanger");
const primaryBtn = document.getElementById("adminConfirmPrimary");

function setLabel(container, text) {
  const label = container?.querySelector("[data-button-text]");
  if (label) label.textContent = text;
}

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-confirm-action]");
  if (!trigger || !form) return;
  const data = trigger.dataset;

  form.action = data.confirmAction;
  if (modalTitle) modalTitle.textContent = data.confirmTitle || "Yakin?";
  if (body) body.textContent = data.confirmBody || "";

  fields.replaceChildren();
  let extra = {};
  try {
    extra = JSON.parse(data.confirmFields || "{}");
  } catch {
    extra = {};
  }
  for (const [name, value] of Object.entries(extra)) {
    const input = document.createElement("input");
    input.type = "hidden";
    input.name = name;
    input.value = value;
    fields.append(input);
  }

  const noteName = data.confirmNote || "";
  noteWrap.hidden = !noteName;
  note.value = "";
  note.name = noteName;
  note.required = data.confirmNoteRequired === "true";
  if (noteName) {
    noteLabel.textContent = data.confirmNoteLabel || "Alasan";
    noteHint.textContent = note.required
      ? "Wajib diisi supaya penulis tahu apa yang perlu diubah."
      : "Opsional. Penulis akan menerima alasan ini lewat notifikasi.";
  }

  const danger = (data.confirmTone || "danger") === "danger";
  dangerBtn.hidden = !danger;
  primaryBtn.hidden = danger;
  setLabel(danger ? dangerBtn : primaryBtn, data.confirmLabel || (danger ? "Hapus" : "Lanjutkan"));

  // Only the visible submit button may send the form
  dangerBtn.querySelector("button")?.toggleAttribute("disabled", !danger);
  primaryBtn.querySelector("button")?.toggleAttribute("disabled", danger);
});

// Fokus ke catatan saat modal terbuka kalau catatannya wajib
document.getElementById("adminConfirmModal")?.addEventListener("modal:open", () => {
  if (!noteWrap.hidden && note.required) setTimeout(() => note.focus(), 50);
});
