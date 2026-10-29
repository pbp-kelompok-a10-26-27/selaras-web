// Donation form (new and edit): quick amounts, a live readout and, on the new-donation page,
// a preview of how the amount moves the campaign's progress bar.
import { setButtonLoading, showMessagesAsToasts } from "../accounts/shared.js";

const money = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 2 });
const percent = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 1 });

const form = document.querySelector("[data-donation-form]");

if (form) {
  init(form);
}

function init(root) {
  const input = root.querySelector("[data-amount-input]");
  const chips = [...root.querySelectorAll("[data-amount-chip]")];
  const readout = root.querySelector("[data-amount-readout]");
  const summary = document.querySelector("[data-donation-summary]");

  const raised = Number(summary?.dataset.raised) || 0;
  const target = Number(summary?.dataset.target) || 0;
  const previewBar = summary?.querySelector("[data-progress-preview]");
  const percentEl = summary?.querySelector("[data-summary-percent]");
  const note = summary?.querySelector("[data-summary-note] span");
  const currentPercent = target > 0 ? Math.min((raised / target) * 100, 100) : 0;

  showMessagesAsToasts();

  function update() {
    const amount = Number(input.value);
    const valid = Number.isFinite(amount) && amount > 0;

    readout.textContent = `Rp ${money.format(valid ? amount : 0)}`;
    chips.forEach((chip) =>
      chip.setAttribute("aria-pressed", String(valid && Number(chip.dataset.amountChip) === amount)),
    );

    if (!summary || target <= 0) return;
    const added = valid ? Math.min((amount / target) * 100, 100 - currentPercent) : 0;
    previewBar.style.width = `${added}%`;
    percentEl.textContent = `${percent.format(currentPercent)}%`;

    note.textContent = !valid
      ? "Pilih nominal untuk melihat dampaknya pada progres kampanye."
      : added <= 0
        ? "Kampanye ini sudah mencapai targetnya. Terima kasih atas dukunganmu!"
        : `Jika disetujui, progres naik menjadi ${percent.format(currentPercent + added)}%.`;
  }

  chips.forEach((chip) =>
    chip.addEventListener("click", () => {
      input.value = chip.dataset.amountChip;
      input.dispatchEvent(new Event("input", { bubbles: true }));
      input.focus();
    }),
  );

  input.addEventListener("input", update);

  root.addEventListener("submit", () => {
    const submit = root.querySelector("button[type='submit']");
    // Disabling right now would drop the click on some browsers; wait a tick
    setTimeout(() => setButtonLoading(submit, true), 0);
  });

  update();
}
