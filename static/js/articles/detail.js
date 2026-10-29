// Article detail: reading progress, remembered text size, copy / native share, toasts, and
// recording a finished read once the reader reaches the end (used by reading challenges).
import { showMessagesAsToasts } from "../accounts/shared.js";

const STORAGE_KEY = "selaras:article-text-size";
const prose = document.querySelector("[data-article-prose]");
const bar = document.querySelector("[data-read-progress]");
const percentEl = document.querySelector("[data-read-percent]");

// ------------------------------------------------------------ progress

function updateProgress() {
  if (!prose) return;
  const rect = prose.getBoundingClientRect();
  const total = rect.height - window.innerHeight * 0.6;
  const read = total > 0 ? (window.innerHeight * 0.4 - rect.top) / total : 1;
  const value = Math.min(Math.max(read, 0), 1);
  bar?.style.setProperty("--read", value.toFixed(3));
  if (percentEl) percentEl.textContent = String(Math.round(value * 100));
}

let ticking = false;
window.addEventListener(
  "scroll",
  () => {
    if (ticking) return;
    ticking = true;
    requestAnimationFrame(() => {
      updateProgress();
      ticking = false;
    });
  },
  { passive: true },
);
window.addEventListener("resize", updateProgress);

// ----------------------------------------------------------- text size

const sizeButtons = [...document.querySelectorAll("[data-text-size]")];

function setTextSize(size, remember = true) {
  if (!prose) return;
  prose.dataset.size = size;
  sizeButtons.forEach((button) =>
    button.setAttribute("aria-pressed", String(button.dataset.textSize === size)),
  );
  if (remember) {
    try {
      localStorage.setItem(STORAGE_KEY, size);
    } catch {
      // Storage can be blocked; the choice just won't be remembered
    }
  }
  updateProgress();
}

sizeButtons.forEach((button) =>
  button.addEventListener("click", () => setTextSize(button.dataset.textSize)),
);

try {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (saved && sizeButtons.some((button) => button.dataset.textSize === saved)) {
    setTextSize(saved, false);
  }
} catch {
  // Ignore unavailable storage
}

// --------------------------------------------------------------- share

const shareUrl = () => window.location.href.split("#")[0];

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

document.querySelector("[data-copy-link]")?.addEventListener("click", async () => {
  const ok = await copyText(shareUrl());
  window.showToast?.(
    ok
      ? { type: "success", title: "Tautan disalin", message: "Tautan artikel siap dibagikan." }
      : { type: "error", title: "Gagal menyalin", message: shareUrl() },
  );
});

const nativeShare = document.querySelector("[data-native-share]");
if (nativeShare && navigator.share) {
  nativeShare.classList.remove("hidden");
  nativeShare.addEventListener("click", () =>
    navigator.share({ title: document.title, url: shareUrl() }).catch(() => {}),
  );
}

// ---------------------------------------------------------- finished read

// Reaching the end counts as a read, but only after a short stay, so scrolling straight
// to the bottom doesn't count
const MIN_SECONDS = 20;
const marker = document.querySelector("[data-read-marker]");
const openedAt = Date.now();

function csrfToken() {
  return document.querySelector('[name="csrfmiddlewaretoken"]')?.value ?? "";
}

async function recordRead() {
  marker.dataset.readSending = "";
  try {
    const response = await fetch(marker.dataset.readUrl, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken(), Accept: "application/json" },
    });
    if (!response.ok) throw new Error(String(response.status));
    const data = await response.json();
    marker.dataset.readDone = "";
    marker.querySelector("[data-read-text]").textContent =
      `Tercatat! Kamu sudah menyelesaikan ${data.total_read} artikel.`;
    if (data.created) {
      window.showToast?.({
        type: "success",
        title: "Bacaan tercatat",
        message: "Progres challenge membacamu ikut bertambah.",
      });
    }
  } catch {
    delete marker.dataset.readSending;
  }
}

if (marker?.dataset.readUrl && !("readDone" in marker.dataset) && "IntersectionObserver" in window) {
  const observer = new IntersectionObserver(
    (entries) => {
      if (!entries.some((entry) => entry.isIntersecting)) return;
      if ("readSending" in marker.dataset || "readDone" in marker.dataset) return;
      const waited = (Date.now() - openedAt) / 1000;
      if (waited < MIN_SECONDS) {
        // Try again when the minimum time is up, if it's still on screen
        setTimeout(() => {
          observer.unobserve(marker);
          observer.observe(marker);
        }, (MIN_SECONDS - waited) * 1000 + 50);
        return;
      }
      observer.disconnect();
      recordRead();
    },
    { threshold: 0.6 },
  );
  observer.observe(marker);
}

showMessagesAsToasts();
updateProgress();
