// New password forms (templates/accounts/_new_password_fields.html, on the change
// password and reset confirm pages): strength meter, live requirement checklist
// and a submit button that waits for them.
import { setButtonLoading, showMessagesAsToasts } from "./shared.js";

const STRENGTH_LABELS = ["Belum diisi", "Lemah", "Cukup", "Bagus", "Kuat"];
const STRENGTH_COLORS = [
  "text-neutral-800",
  "text-tertiary-700",
  "text-secondary-700",
  "text-primary-700",
  "text-secondary-600",
];

const form = document.querySelector("[data-password-form]");

// 0 (empty) to 4 (strong). Only a hint: Django's validators decide on submit
function scorePassword(value) {
  if (!value) return 0;
  let score = 0;
  if (value.length >= 8) score += 1;
  if (value.length >= 12) score += 1;
  if (/[a-z]/.test(value) && /[A-Z]/.test(value)) score += 1;
  if (/\d/.test(value)) score += 1;
  if (/[^A-Za-z0-9]/.test(value)) score += 1;
  if (/^\d+$/.test(value) || value.length < 8) score = Math.min(score, 1);
  return Math.max(1, Math.min(4, score));
}

if (form) {
  const current = form.querySelector("#id_old_password");
  const password = form.querySelector("#id_new_password1");
  const confirm = form.querySelector("#id_new_password2");
  const submit = form.querySelector('button[type="submit"]');
  const bars = form.querySelectorAll("[data-strength-bar]");
  const label = form.querySelector("[data-strength-label]");
  const rules = Object.fromEntries(
    [...form.querySelectorAll("[data-rule]")].map((rule) => [rule.dataset.rule, rule]),
  );

  function update() {
    const value = password.value;
    const score = scorePassword(value);

    bars.forEach((bar, index) => {
      if (index < score) bar.dataset.level = score;
      else delete bar.dataset.level;
    });
    label.textContent = STRENGTH_LABELS[score];
    label.className = `font-semibold ${STRENGTH_COLORS[score]}`;

    const met = {
      length: value.length >= 8,
      numeric: Boolean(value) && !/^\d+$/.test(value),
      mixed: /[A-Za-z]/.test(value) && /[^A-Za-z]/.test(value),
      match: Boolean(value) && value === confirm.value,
    };
    Object.entries(met).forEach(([name, ok]) => {
      rules[name].dataset.met = String(ok);
    });

    // Mismatch shows only once the confirmation is as long as the password
    const mismatch = confirm.value.length >= value.length && confirm.value && !met.match;
    confirm.classList.toggle("border-tertiary-600", Boolean(mismatch));
    if (mismatch) confirm.setAttribute("aria-invalid", "true");
    else confirm.removeAttribute("aria-invalid");

    // The reset confirm page has no current password field
    const hasCurrent = !current || Boolean(current.value);
    submit.disabled = !(hasCurrent && met.length && met.numeric && met.match);
  }

  form.addEventListener("input", update);
  form.addEventListener("submit", (event) => {
    if (submit.disabled) {
      event.preventDefault();
      return;
    }
    setButtonLoading(submit);
  });

  update();
}

showMessagesAsToasts();
