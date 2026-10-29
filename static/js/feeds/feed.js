// Feed pages (list, detail, create): optimistic likes on posts and comments, who-liked
// dialog, photo carousel, replies, share link, "read more", relative times, double-tap
// to like and submit loading. Everything also works without this script:
// likes are plain forms and every link is a real link.
import {
  prefersReducedMotion,
  revealOnScroll,
  setButtonLoading,
  showMessagesAsToasts,
} from "../accounts/shared.js";
import { renderRelativeTimes } from "../components/relative-time/relative-time.js";

const toast = (type, title, message) => window.showToast?.({ type, title, message });

// ------------------------------------------------------------------ likes

function paintLike(button, liked, count) {
  const form = button.closest("form");
  const subject = form.dataset.likeSubject || "postingan";
  button.setAttribute("aria-pressed", String(liked));
  button.setAttribute("aria-label", `${liked ? "Batalkan suka" : "Sukai"} ${subject} ini`);
  const label = button.querySelector("[data-like-label]");
  if (label) label.textContent = liked ? "Disukai" : "Suka";
  button.querySelector("[data-like-count]").textContent = String(count);
  form.querySelector('[name="action"]').value = liked ? "unlike" : "like";

  if (liked && !prefersReducedMotion()) {
    button.dataset.bump = "";
    button.addEventListener("animationend", () => delete button.dataset.bump, {
      once: true,
    });
  }
}

async function toggleLike(form) {
  const button = form.querySelector("button[type='submit']");
  if (button.dataset.busy) return;

  const wasLiked = button.getAttribute("aria-pressed") === "true";
  const before = Number(button.querySelector("[data-like-count]").textContent) || 0;
  button.dataset.busy = "true";
  paintLike(button, !wasLiked, Math.max(before + (wasLiked ? -1 : 1), 0));

  try {
    const response = await fetch(form.dataset.apiUrl, {
      method: wasLiked ? "DELETE" : "POST",
      credentials: "same-origin",
      headers: {
        Accept: "application/json",
        "X-CSRFToken": form.querySelector('[name="csrfmiddlewaretoken"]').value,
      },
    });
    if (!response.ok) throw new Error(String(response.status));
    const { data } = await response.json();
    paintLike(button, data.liked, data.like_count);
  } catch {
    paintLike(button, wasLiked, before);
    toast("error", "Gagal memperbarui suka", "Coba lagi sebentar lagi.");
  } finally {
    delete button.dataset.busy;
  }
}

document.addEventListener("submit", (event) => {
  const form = event.target.closest?.("form[data-like-form]");
  if (!form) return;
  event.preventDefault();
  toggleLike(form);
});

// ------------------------------------------------------------- share link

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
  const button = event.target.closest?.("[data-copy-link]");
  if (!button) return;

  const url = new URL(button.dataset.copyLink, window.location.origin).href;
  if (await copyText(url)) {
    toast("success", "Tautan disalin", "Tautan postingan siap kamu bagikan.");
  } else {
    toast("error", "Gagal menyalin", url);
  }
});

// ---------------------------------------------------------- double-tap like

document.addEventListener("dblclick", (event) => {
  const body = event.target.closest?.("[data-doubletap]");
  if (!body) return;

  const post = body.closest("[data-post]");
  const likeButton = post?.querySelector("[data-like-form] button[type='submit']");
  if (!likeButton) return;

  body.dataset.popping = "";
  body.addEventListener("animationend", () => delete body.dataset.popping, {
    once: true,
  });
  if (likeButton.getAttribute("aria-pressed") !== "true") likeButton.form.requestSubmit();
});

// ------------------------------------------------------------ who liked

const likersModal = document.getElementById("likers-modal");
const likersBody = likersModal?.querySelector("[data-likers-body]");
const LIKERS_LOADING =
  '<div class="space-y-2 p-2" aria-hidden="true"><div class="h-10 animate-pulse rounded-xl bg-neutral-300"></div><div class="h-10 animate-pulse rounded-xl bg-neutral-300"></div><div class="h-10 animate-pulse rounded-xl bg-neutral-300"></div></div>';
const LIKERS_FAILED =
  '<p class="px-2 py-6 text-center font-sans text-sm text-neutral-800">Daftar belum dapat dimuat. Coba lagi sebentar lagi.</p>';

async function loadLikers(url, { append = false } = {}) {
  const response = await fetch(url, {
    headers: { Accept: "text/html" },
    credentials: "same-origin",
  });
  if (!response.ok) throw new Error(String(response.status));
  const holder = document.createElement("div");
  holder.innerHTML = await response.text();
  renderRelativeTimes(holder);
  if (!append) {
    likersBody.replaceChildren(...holder.childNodes);
    return;
  }
  likersBody.querySelector("[data-likers-more-wrap]")?.remove();
  const list = likersBody.querySelector("[data-likers-list]");
  list?.append(...(holder.querySelector("[data-likers-list]")?.children ?? []));
  const more = holder.querySelector("[data-likers-more-wrap]");
  if (more) likersBody.append(more);
}

document.addEventListener("click", async (event) => {
  const more = event.target.closest?.("[data-likers-more]");
  if (more && likersBody?.contains(more)) {
    more.disabled = true;
    await loadLikers(more.dataset.likersMore, { append: true }).catch(() => {
      more.disabled = false;
    });
    return;
  }

  const trigger = event.target.closest?.("[data-likers-url]");
  if (!trigger || !likersModal) return;
  likersModal.querySelector("#likers-modal-title").textContent =
    trigger.dataset.likersTitle || "Disukai oleh";
  likersBody.innerHTML = LIKERS_LOADING;
  window.openModal?.("likers-modal");
  try {
    await loadLikers(trigger.dataset.likersUrl);
  } catch {
    likersBody.innerHTML = LIKERS_FAILED;
  }
});

// --------------------------------------------------------------- carousel

function initCarousel(root) {
  const track = root.querySelector("[data-carousel-track]");
  const slides = [...track.children];
  const counter = root.querySelector("[data-carousel-counter]");
  const dots = [...root.querySelectorAll("[data-carousel-dot]")];
  const prev = root.querySelector("[data-carousel-prev]");
  const next = root.querySelector("[data-carousel-next]");
  let current = -1;

  const go = (index) => {
    const target = Math.min(Math.max(index, 0), slides.length - 1);
    track.scrollTo({
      left: slides[target].offsetLeft,
      behavior: prefersReducedMotion() ? "auto" : "smooth",
    });
  };

  const paint = () => {
    const index = Math.round(track.scrollLeft / Math.max(track.clientWidth, 1));
    if (index === current) return;
    current = index;
    counter.textContent = `${index + 1}/${slides.length}`;
    // With more photos than dots, the last dot stands for the rest
    const dotIndex = Math.min(index, dots.length - 1);
    dots.forEach((dot, i) => dot.setAttribute("aria-current", String(i === dotIndex)));
    prev.disabled = index === 0;
    next.disabled = index === slides.length - 1;
  };

  let frame;
  track.addEventListener(
    "scroll",
    () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(paint);
    },
    { passive: true },
  );
  prev.addEventListener("click", () => go(current - 1));
  next.addEventListener("click", () => go(current + 1));
  track.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft") go(current - 1);
    else if (event.key === "ArrowRight") go(current + 1);
    else return;
    event.preventDefault();
  });
  paint();
}

document.querySelectorAll("[data-carousel]").forEach(initCarousel);

// ---------------------------------------------------------------- replies

function autoGrow(input) {
  input.style.height = "auto";
  input.style.height = `${input.scrollHeight}px`;
}

function openReply(button) {
  const form = document.getElementById(`reply-form-${button.dataset.replyTo}`);
  if (!form) return;
  const input = form.querySelector("[data-reply-input]");
  const mention = button.dataset.replyMention;
  form.querySelector("[data-reply-target]").textContent = button.dataset.replyName;
  document.querySelectorAll("[data-reply-form].is-open").forEach((other) => {
    if (other !== form && !other.querySelector("[data-reply-input]").value.trim()) {
      other.classList.remove("is-open");
    }
  });
  form.classList.add("is-open");
  // Replying to a reply mentions its author, like Instagram
  if (mention && !input.value.includes(`@${mention}`)) {
    input.value = `@${mention} ${input.value.trim()}`.trimEnd() + " ";
  }
  input.focus();
  input.setSelectionRange(input.value.length, input.value.length);
  autoGrow(input);
}

function setRepliesExpanded(toggle, expanded) {
  toggle.closest("[data-replies]").querySelectorAll("[data-reply-extra]").forEach((item) => {
    item.hidden = !expanded;
  });
  toggle.setAttribute("aria-expanded", String(expanded));
  toggle.querySelector("[data-replies-toggle-label]").textContent = expanded
    ? "Sembunyikan balasan"
    : `Lihat ${toggle.dataset.hiddenCount} balasan lainnya`;
}

document.addEventListener("click", (event) => {
  const reply = event.target.closest?.("[data-reply-to]");
  if (reply) {
    openReply(reply);
    return;
  }
  const cancel = event.target.closest?.("[data-reply-cancel]");
  if (cancel) {
    const form = cancel.closest("[data-reply-form]");
    form.classList.remove("is-open");
    form.reset();
    return;
  }
  const toggle = event.target.closest?.("[data-replies-toggle]");
  if (toggle) setRepliesExpanded(toggle, toggle.getAttribute("aria-expanded") !== "true");
});

document.addEventListener("input", (event) => {
  if (event.target.matches?.("[data-reply-input]")) autoGrow(event.target);
});

// Enter sends a reply, Shift+Enter adds a new line
document.addEventListener("keydown", (event) => {
  const input = event.target.closest?.("[data-reply-input]");
  if (!input || event.key !== "Enter" || event.shiftKey || event.isComposing) return;
  event.preventDefault();
  if (input.value.trim()) input.form.requestSubmit();
});

// Long threads start collapsed, unless the link points at one of the hidden replies
function collapseReplies() {
  let target = null;
  try {
    target = window.location.hash ? document.querySelector(window.location.hash) : null;
  } catch {
    target = null;
  }
  document.querySelectorAll("[data-replies-toggle]").forEach((toggle) => {
    const extra = [...toggle.closest("[data-replies]").querySelectorAll("[data-reply-extra]")];
    toggle.classList.remove("hidden");
    toggle.classList.add("inline-flex");
    setRepliesExpanded(toggle, Boolean(target && extra.some((item) => item.contains(target))));
  });
  target?.scrollIntoView({ block: "center" });
}

// -------------------------------------------------------------- read more

function markClamped() {
  document.querySelectorAll("[data-clamp]").forEach((text) => {
    const more = text.parentElement.querySelector("[data-clamp-more]");
    if (more) more.hidden = text.scrollHeight <= text.clientHeight + 1;
  });
}

// ----------------------------------------------------------- form loading

document.addEventListener("submit", (event) => {
  const form = event.target.closest?.("form[data-submit-loading]");
  if (!form) return;

  const submit =
    form.querySelector("button[type='submit']") ??
    document.querySelector(`button[type='submit'][form='${form.id}']`);
  // Disabling right now would drop the click on some browsers; wait a tick
  setTimeout(() => setButtonLoading(submit, true), 0);
});

// ------------------------------------------------------------------- init

showMessagesAsToasts();
revealOnScroll();
renderRelativeTimes();
collapseReplies();
markClamped();
setInterval(renderRelativeTimes, 60_000);

let resizeTimer;
window.addEventListener("resize", () => {
  clearTimeout(resizeTimer);
  resizeTimer = setTimeout(markClamped, 150);
});
document.fonts?.ready.then(markClamped);
