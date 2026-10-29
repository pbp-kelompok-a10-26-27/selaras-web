// Admin challenges list: filter dropdown auto-submit, delete confirmation, toasts.
import { showMessagesAsToasts } from "../accounts/shared.js";

showMessagesAsToasts();

const filterForm = document.getElementById("adminChallengesFilter");
const statusInput = document.getElementById("adminChallengesStatus");

// The dropdown component fires "change" on its hidden input
statusInput?.addEventListener("change", () => filterForm?.submit());

const deleteForm = document.getElementById("deleteChallengeForm");
const titleEl = document.getElementById("deleteModalChallengeTitle");
const warningEl = document.getElementById("deleteModalParticipantWarning");
const countEl = document.getElementById("deleteModalParticipantsCount");
const safeNoticeEl = document.getElementById("deleteModalSafeNotice");
const confirmEl = document.getElementById("deleteConfirmBtnContainer");

document.querySelectorAll("[data-delete-trigger]").forEach((trigger) => {
  trigger.addEventListener("click", () => {
    const row = trigger.closest("[data-delete-url]");
    if (!row) return;

    const participants = Number.parseInt(row.dataset.challengeParticipants, 10) || 0;
    const blocked = participants > 0;

    if (deleteForm) deleteForm.action = row.dataset.deleteUrl;
    if (titleEl) titleEl.textContent = `\u201c${row.dataset.challengeTitle}\u201d`;
    if (countEl) countEl.textContent = participants;

    warningEl?.classList.toggle("hidden", !blocked);
    warningEl?.classList.toggle("flex", blocked);
    safeNoticeEl?.classList.toggle("hidden", blocked);
    safeNoticeEl?.classList.toggle("flex", !blocked);
    confirmEl?.classList.toggle("hidden", blocked);
  });
});
