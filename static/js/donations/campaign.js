// Donation pages that show a campaign or a donation (detail, history, edit): toasts for
// Django messages, a count-up for the raised amount, and "copy link". The server already
// renders the final numbers, so the page is complete without this script.
import {
  prefersReducedMotion,
  revealOnScroll,
  showMessagesAsToasts,
} from "../accounts/shared.js";

const money = new Intl.NumberFormat("id-ID", { maximumFractionDigits: 0 });

function countUp(node) {
  const target = Number(node.dataset.countup);
  if (!Number.isFinite(target) || target <= 0 || prefersReducedMotion()) return;

  const prefix = node.dataset.prefix ?? "";
  const duration = 1200;
  let start = null;

  function frame(now) {
    start ??= now;
    const progress = Math.min((now - start) / duration, 1);
    const eased = 1 - (1 - progress) ** 4;
    node.textContent = `${prefix}${money.format(Math.round(target * eased))}`;
    if (progress < 1) requestAnimationFrame(frame);
  }

  node.textContent = `${prefix}0`;
  requestAnimationFrame(frame);
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    return true;
  } catch {
    const field = Object.assign(document.createElement("textarea"), {
      value: text,
      readOnly: true,
    });
    field.style.cssText = "position:fixed;opacity:0";
    document.body.append(field);
    field.select();
    const ok = document.execCommand("copy");
    field.remove();
    return ok;
  }
}

document.addEventListener("click", async (event) => {
  if (!event.target.closest("[data-copy-link]")) return;
  const ok = await copyText(window.location.href.split("#")[0]);
  window.showToast?.(
    ok
      ? { type: "success", title: "Tautan disalin", message: "Tautan kampanye siap dibagikan." }
      : { type: "error", title: "Gagal menyalin", message: window.location.href },
  );
});

showMessagesAsToasts();
revealOnScroll();
document.querySelectorAll("[data-countup]").forEach(countUp);
