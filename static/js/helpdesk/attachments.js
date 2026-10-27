// Ticket screenshots, in three parts:
//  - createAttachmentPicker: the drop zone, paste and "image link" field of the create
//    ticket dialog (templates/helpdesk/helpdesk.html), with thumbnails you can remove
//  - createAttachmentGallery: the thumbnails on a ticket page
//  - openImageViewer: the full-size viewer both of them open
import { createIcon, el, renderLucideIcons } from "./shared.js";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const URL_MAX_LENGTH = 500;

const formatSize = (bytes) =>
  bytes < 1024 * 1024 ? `${Math.max(1, Math.round(bytes / 1024))} KB` : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;

function hostOf(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url;
  }
}

function isHttpUrl(value) {
  try {
    return ["http:", "https:"].includes(new URL(value).protocol);
  } catch {
    return false;
  }
}

// Shows `src`; when an image link is broken or isn't a picture, swaps in a link card so
// the tile still tells you where it points
function createThumbnail(src, { label, fit = "object-cover", lazy = true }) {
  const frame = el("div", "relative h-full w-full overflow-hidden bg-neutral-400");
  const image = el("img", `h-full w-full ${fit} transition-transform duration-300`);
  image.src = src;
  image.alt = label;
  image.loading = lazy ? "lazy" : "eager";
  image.decoding = "async";
  // Links point at other sites: don't tell them which page you came from
  image.referrerPolicy = "no-referrer";
  image.draggable = false;

  image.addEventListener("error", () => {
    frame.replaceChildren();
    frame.classList.add("flex", "flex-col", "items-center", "justify-center", "gap-1", "p-2", "text-center");
    frame.append(
      createIcon("image-off", "w-6 h-6 text-neutral-800"),
      el("span", "line-clamp-2 break-all font-sans text-[0.6875rem] text-neutral-900", hostOf(src)),
    );
    renderLucideIcons(frame);
  });

  frame.append(image);
  return frame;
}

/* ================================ VIEWER ================================ */

let viewer = null;

// Full-size viewer for `items` ([{url, name}]) starting at `index`. Arrow keys move,
// Escape closes and focus returns to whatever opened it.
export function openImageViewer(items, index = 0) {
  if (viewer || !items.length) return;
  const opener = document.activeElement;
  let current = index;

  const overlay = el(
    "div",
    "fixed inset-0 z-[60] flex flex-col bg-neutral-900/90 opacity-0 backdrop-blur-sm transition-opacity duration-200",
  );
  overlay.setAttribute("role", "dialog");
  overlay.setAttribute("aria-modal", "true");
  overlay.setAttribute("aria-label", "Image viewer");

  const iconButton = (icon, label, extra = "") => {
    const button = el(
      "button",
      `flex h-11 w-11 cursor-pointer items-center justify-center rounded-full bg-neutral-50/10 text-neutral-50 outline-none transition-colors hover:bg-neutral-50/25 focus-visible:ring-2 focus-visible:ring-primary-300 ${extra}`,
    );
    button.type = "button";
    button.setAttribute("aria-label", label);
    button.append(createIcon(icon, "w-5 h-5"));
    return button;
  };

  const counter = el("p", "font-sans text-sm font-semibold text-neutral-50 tabular-nums");
  counter.setAttribute("aria-live", "polite");
  const openLink = el(
    "a",
    "flex h-11 items-center gap-2 rounded-full bg-neutral-50/10 px-4 font-sans text-sm font-semibold text-neutral-50 outline-none transition-colors hover:bg-neutral-50/25 focus-visible:ring-2 focus-visible:ring-primary-300",
  );
  openLink.target = "_blank";
  openLink.rel = "noopener noreferrer";
  openLink.append(createIcon("external-link", "w-4 h-4"), el("span", "max-sm:sr-only", "Open original"));
  const close = iconButton("x", "Close viewer (Esc)");

  const bar = el("div", "flex items-center justify-between gap-3 p-3 sm:p-4");
  const actions = el("div", "flex items-center gap-2");
  actions.append(openLink, close);
  bar.append(counter, actions);

  const stage = el("div", "relative flex min-h-0 flex-1 items-center justify-center px-3 pb-4 sm:px-16");
  const picture = el("img", "max-h-full max-w-full rounded-xl object-contain shadow-2xl transition-opacity duration-200");
  picture.referrerPolicy = "no-referrer";
  const fallback = el("p", "hidden max-w-sm text-center font-sans text-sm text-neutral-50");
  const previous = iconButton("chevron-left", "Previous image", "absolute left-2 sm:left-4");
  const next = iconButton("chevron-right", "Next image", "absolute right-2 sm:right-4");
  stage.append(picture, fallback, previous, next);
  overlay.append(bar, stage);

  function show(position) {
    current = (position + items.length) % items.length;
    const item = items[current];
    picture.style.opacity = "0";
    fallback.classList.add("hidden");
    picture.classList.remove("hidden");
    picture.src = item.url;
    picture.alt = item.name;
    openLink.href = item.url;
    counter.textContent = items.length > 1 ? `${current + 1} / ${items.length}` : item.name;
    previous.hidden = next.hidden = items.length < 2;
  }

  picture.addEventListener("load", () => {
    picture.style.opacity = "1";
  });
  picture.addEventListener("error", () => {
    picture.classList.add("hidden");
    fallback.classList.remove("hidden");
    fallback.textContent = "This image couldn't be loaded. It may have been removed, or the link may not point to a picture.";
  });

  function onKey(event) {
    if (event.key === "Escape") {
      event.stopPropagation();
      closeViewer();
    } else if (event.key === "ArrowLeft") show(current - 1);
    else if (event.key === "ArrowRight") show(current + 1);
    else if (event.key === "Tab") {
      // Keep Tab inside the viewer
      const focusable = [...overlay.querySelectorAll("button:not([hidden]), a[href]")];
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    }
  }

  function closeViewer() {
    document.removeEventListener("keydown", onKey, true);
    overlay.classList.add("opacity-0");
    setTimeout(() => overlay.remove(), 200);
    document.body.style.overflow = overlay.dataset.previousOverflow;
    viewer = null;
    opener?.focus?.();
  }

  previous.addEventListener("click", () => show(current - 1));
  next.addEventListener("click", () => show(current + 1));
  close.addEventListener("click", closeViewer);
  // Clicking the dark area (not the picture or a button) closes it
  stage.addEventListener("click", (event) => {
    if (event.target === stage) closeViewer();
  });

  overlay.dataset.previousOverflow = document.body.style.overflow;
  document.body.style.overflow = "hidden";
  document.body.append(overlay);
  renderLucideIcons(overlay);
  show(current);
  document.addEventListener("keydown", onKey, true);
  requestAnimationFrame(() => {
    overlay.classList.remove("opacity-0");
    close.focus();
  });
  viewer = overlay;
}

/* ================================ GALLERY ================================ */

// Thumbnails of a ticket's attachments: [{id, kind: "file" | "link", url}]
export function createAttachmentGallery(attachments) {
  if (!attachments?.length) return null;

  const items = attachments.map((attachment, position) => ({
    url: attachment.url,
    kind: attachment.kind,
    name: attachment.kind === "link" ? hostOf(attachment.url) : `Screenshot ${position + 1}`,
  }));

  const section = el("section", "flex flex-col gap-3");
  section.setAttribute("aria-label", "Attachments");
  const heading = el("h2", "flex items-center gap-2 font-sans text-sm font-semibold text-foreground");
  heading.append(
    createIcon("paperclip", "w-4 h-4 text-secondary-500"),
    document.createTextNode(`Attachments (${items.length})`),
  );

  const list = el("ul", "grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4");
  items.forEach((item, position) => {
    const entry = el("li");
    const button = el(
      "button",
      "group relative block aspect-4/3 w-full cursor-zoom-in overflow-hidden rounded-2xl border border-neutral-400 bg-neutral-300 outline-none transition-all duration-200 hover:-translate-y-0.5 hover:border-primary-400 hover:shadow-md focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-2",
    );
    button.type = "button";
    button.setAttribute("aria-label", `View ${item.name} full size`);
    button.append(createThumbnail(item.url, { label: item.name }));

    if (item.kind === "link") {
      const badge = el(
        "span",
        "absolute bottom-2 left-2 flex max-w-[calc(100%-1rem)] items-center gap-1 rounded-full bg-neutral-900/70 px-2 py-0.5 font-sans text-[0.6875rem] font-semibold text-neutral-50 backdrop-blur-sm",
      );
      badge.append(createIcon("link", "w-3 h-3 shrink-0"), el("span", "truncate", item.name));
      button.append(badge);
    }
    const zoom = el(
      "span",
      "absolute top-2 right-2 flex h-8 w-8 items-center justify-center rounded-full bg-neutral-900/60 text-neutral-50 opacity-0 transition-opacity duration-200 group-hover:opacity-100 group-focus-visible:opacity-100",
    );
    zoom.append(createIcon("maximize-2", "w-4 h-4"));
    button.append(zoom);

    button.addEventListener("click", () => openImageViewer(items, position));
    entry.append(button);
    list.append(entry);
  });

  section.append(heading, list);
  renderLucideIcons(section);
  return section;
}

/* ================================ PICKER ================================ */

const prefersReducedMotion = () => window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const plural = (count, noun) => `${count} ${noun}${count === 1 ? "" : "s"}`;

// root: the [data-attachments] block. Returns what the form needs: how many files and
// links are attached, how to add them to the request body, upload progress, and how
// to start over.
export function createAttachmentPicker(root) {
  const maxItems = Number(root.dataset.max);
  const maxBytes = Number(root.dataset.maxMb) * 1024 * 1024;
  const drop = root.querySelector("[data-attach-drop]");
  const fileInput = root.querySelector("[data-attach-file]");
  const linkInput = root.querySelector("[data-attach-link]");
  const linkAdd = root.querySelector("[data-attach-link-add]");
  const list = root.querySelector("[data-attach-list]");
  const counter = root.querySelector("[data-attach-count]");
  const status = root.querySelector("[data-attach-status]");
  const statusText = root.querySelector("[data-attach-status-text]");
  const errorBox = root.querySelector("[data-attach-error]");
  const preview = {
    box: root.querySelector("[data-link-preview]"),
    image: root.querySelector("[data-link-preview-image]"),
    spinner: root.querySelector("[data-link-preview-spinner]"),
    broken: root.querySelector("[data-link-preview-broken]"),
    host: root.querySelector("[data-link-preview-host]"),
    text: root.querySelector("[data-link-preview-text]"),
  };

  let items = []; // {id, kind: "file" | "link", file?, url, name, size?, preview, tile}
  let nextId = 1;
  let uploading = null; // upload progress (0..1) while the ticket is being sent

  // Without this script the two inputs post their values themselves. From here on
  // appendTo() sends them instead, so drop the names to avoid sending them twice.
  fileInput.removeAttribute("name");
  linkInput.removeAttribute("name");

  function setError(message) {
    errorBox.hidden = !message;
    errorBox.textContent = message ?? "";
  }

  // Counter, "N attached" line, compact drop zone and limits
  function updateSummary() {
    const files = items.filter((item) => item.kind === "file").length;
    const links = items.length - files;
    const full = items.length >= maxItems;

    counter.textContent = `${items.length} / ${maxItems}`;
    counter.classList.toggle("text-primary-800", items.length > 0);
    counter.classList.toggle("font-semibold", items.length > 0);
    root.dataset.hasItems = String(items.length > 0);
    drop.dataset.full = String(full);
    fileInput.disabled = full;
    linkAdd.disabled = full;
    linkAdd.classList.toggle("opacity-45", full);
    linkAdd.classList.toggle("pointer-events-none", full);

    status.hidden = items.length === 0;
    if (uploading !== null) {
      statusText.textContent = `Uploading ${plural(items.length, "attachment")}… ${Math.round(uploading * 100)}%`;
      return;
    }
    const parts = [];
    if (files) parts.push(plural(files, "image"));
    if (links) parts.push(plural(links, "link"));
    statusText.textContent = `${parts.join(" and ")} attached${full ? " (the limit)" : ""}. They'll be sent with your ticket.`;
  }

  function createTile(item) {
    const tile = el(
      "li",
      "group relative aspect-4/3 overflow-hidden rounded-2xl border border-primary-300 bg-neutral-300 shadow-sm",
    );
    tile.append(createThumbnail(item.preview, { label: item.name, lazy: false }));

    const badge = el(
      "span",
      "absolute top-1.5 left-1.5 flex items-center gap-1 rounded-full bg-primary-500 px-2 py-0.5 font-sans text-[0.6875rem] font-semibold text-neutral-50 shadow-sm",
    );
    badge.append(createIcon("check", "w-3 h-3"), document.createTextNode("Attached"));

    const caption = el(
      "div",
      "absolute inset-x-0 bottom-0 flex items-center gap-1.5 bg-linear-to-t from-neutral-900/80 to-transparent px-2.5 pt-6 pb-2 font-sans text-[0.6875rem] font-semibold text-neutral-50",
    );
    caption.append(
      createIcon(item.kind === "link" ? "link" : "image", "w-3 h-3 shrink-0"),
      el("span", "min-w-0 flex-1 truncate", item.name),
      el("span", "shrink-0 font-normal opacity-80", item.kind === "link" ? "Link" : formatSize(item.size)),
    );

    // Filled while the ticket uploads (files only: links are just text)
    item.progress = el("span", "absolute inset-x-0 bottom-0 hidden h-1 bg-neutral-900/30");
    item.progressFill = el("span", "block h-full w-0 bg-primary-300 transition-[width] duration-200");
    item.progress.append(item.progressFill);

    const remove = el(
      "button",
      "absolute top-1.5 right-1.5 flex h-8 w-8 cursor-pointer items-center justify-center rounded-full bg-neutral-900/65 text-neutral-50 outline-none backdrop-blur-sm transition-all duration-150 hover:scale-110 hover:bg-red-100 focus-visible:ring-2 focus-visible:ring-primary-300",
    );
    remove.type = "button";
    remove.setAttribute("aria-label", `Remove ${item.name}`);
    remove.append(createIcon("x", "w-4 h-4"));
    remove.addEventListener("click", () => removeItem(item.id));

    tile.append(badge, caption, item.progress, remove);
    renderLucideIcons(tile);
    return tile;
  }

  function addItem(item) {
    items.push(item);
    item.tile = createTile(item);
    list.append(item.tile);
  }

  // After adding: pop the new tiles in and bring them into view, since the dialog
  // scrolls and they could otherwise land out of sight
  function revealNew(added) {
    updateSummary();
    if (!added.length) return;
    added.forEach(({ tile }) => tile.classList.add("attach-tile-in"));
    requestAnimationFrame(() =>
      added[added.length - 1].tile.scrollIntoView({
        block: "nearest",
        behavior: prefersReducedMotion() ? "auto" : "smooth",
      }),
    );
  }

  function removeItem(id) {
    const item = items.find((entry) => entry.id === id);
    if (!item) return;
    if (item.kind === "file") URL.revokeObjectURL(item.preview);
    item.tile.remove();
    items = items.filter((entry) => entry.id !== id);
    setError("");
    updateSummary();
  }

  function addFiles(files) {
    setError("");
    const problems = [];
    const added = [];
    for (const file of files) {
      if (items.length >= maxItems) {
        problems.push(`You can attach up to ${maxItems} images or links.`);
        break;
      }
      if (!ACCEPTED_TYPES.includes(file.type)) {
        problems.push(`${file.name || "That file"} isn't a JPG, PNG, WebP or GIF image.`);
        continue;
      }
      if (file.size > maxBytes) {
        problems.push(`${file.name} is larger than ${root.dataset.maxMb} MB.`);
        continue;
      }
      const item = {
        id: nextId++,
        kind: "file",
        file,
        name: file.name || "Pasted image",
        size: file.size,
        preview: URL.createObjectURL(file),
      };
      addItem(item);
      added.push(item);
    }
    if (problems.length) setError([...new Set(problems)].join(" "));
    revealNew(added);
  }

  // ---- Live preview of the link being typed ----
  let previewTimer = 0;
  let previewToken = 0;

  function setPreviewState(state, text) {
    preview.box.dataset.state = state;
    preview.text.textContent = text;
    preview.spinner.classList.toggle("hidden", state !== "loading");
    preview.image.classList.toggle("hidden", state !== "ok");
    preview.broken.hidden = state !== "error";
  }

  function hidePreview() {
    clearTimeout(previewTimer);
    previewToken += 1;
    preview.box.hidden = true;
    preview.image.removeAttribute("src");
  }

  function showPreview(url) {
    const token = ++previewToken;
    preview.box.hidden = false;
    preview.host.textContent = hostOf(url);
    setPreviewState("loading", "Loading preview…");

    // Loaded off-screen first, so a broken link never flashes a broken image
    const probe = new Image();
    probe.referrerPolicy = "no-referrer";
    probe.onload = () => {
      if (token !== previewToken) return;
      preview.image.src = url;
      setPreviewState("ok", `Image found · ${probe.naturalWidth} × ${probe.naturalHeight}px`);
    };
    probe.onerror = () => {
      if (token !== previewToken) return;
      setPreviewState("error", "No preview. The link may not point straight to an image, but you can still attach it.");
    };
    probe.src = url;
  }

  linkInput.addEventListener("input", () => {
    clearTimeout(previewTimer);
    const value = linkInput.value.trim();
    if (!value || !isHttpUrl(value) || value.length > URL_MAX_LENGTH) {
      hidePreview();
      return;
    }
    previewTimer = setTimeout(() => showPreview(value), 350);
  });

  function addLink() {
    const value = linkInput.value.trim();
    if (!value) {
      linkInput.focus();
      return;
    }
    setError("");
    if (items.length >= maxItems) return setError(`You can attach up to ${maxItems} images or links.`);
    if (value.length > URL_MAX_LENGTH) return setError(`Links are limited to ${URL_MAX_LENGTH} characters.`);
    if (!isHttpUrl(value)) return setError("Paste a full link that starts with http:// or https://.");
    if (items.some((item) => item.url === value)) return setError("You've already added that link.");

    const item = { id: nextId++, kind: "link", url: value, name: hostOf(value), preview: value };
    addItem(item);
    linkInput.value = "";
    hidePreview();
    revealNew([item]);
    linkInput.focus({ preventScroll: true });
  }

  // ---- Events ----
  fileInput.addEventListener("change", () => {
    addFiles([...fileInput.files]);
    fileInput.value = ""; // picking the same file again should still fire "change"
  });

  let dragDepth = 0;
  const hasFiles = (event) => [...(event.dataTransfer?.types ?? [])].includes("Files");
  const setDragging = (on) => {
    drop.dataset.dragging = String(on);
  };

  // Files can be dropped anywhere on the dialog, not only on the drop zone: a drop
  // that misses it would otherwise make the browser open the image instead
  const dialog = root.closest(".modal-backdrop") ?? root;
  dialog.addEventListener("dragenter", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth += 1;
    setDragging(true);
  });
  dialog.addEventListener("dragover", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    event.dataTransfer.dropEffect = "copy";
  });
  dialog.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) setDragging(false);
  });
  dialog.addEventListener("drop", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth = 0;
    setDragging(false);
    addFiles([...event.dataTransfer.files]);
  });

  // Paste a screenshot straight into the dialog (text pastes are left alone)
  document.addEventListener("paste", (event) => {
    if (dialog.inert) return;
    const images = [...(event.clipboardData?.files ?? [])].filter((file) => file.type.startsWith("image/"));
    if (!images.length) return;
    event.preventDefault();
    addFiles(images);
  });

  linkAdd.addEventListener("click", addLink);
  linkInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter") {
      // Enter adds the link; Ctrl+Enter still submits the whole ticket
      if (event.ctrlKey || event.metaKey) return;
      event.preventDefault();
      event.stopPropagation();
      addLink();
    }
  });

  updateSummary();

  return {
    get count() {
      return items.length;
    },
    get hasFiles() {
      return items.some((item) => item.kind === "file");
    },
    setError,
    // fraction: 0..1 while uploading, null once it's done or failed
    setUploadProgress(fraction) {
      uploading = fraction;
      items.forEach((item) => {
        if (item.kind !== "file") return;
        item.progress.classList.toggle("hidden", fraction === null);
        item.progressFill.style.width = `${Math.round((fraction ?? 0) * 100)}%`;
      });
      updateSummary();
    },
    // Adds the files and links under the names the server reads
    appendTo(formData) {
      items.forEach((item) => {
        if (item.kind === "file") formData.append("attachments", item.file, item.file.name || "pasted.png");
        else formData.append("image_links", item.url);
      });
    },
    reset() {
      items.forEach((item) => item.kind === "file" && URL.revokeObjectURL(item.preview));
      items = [];
      list.replaceChildren();
      linkInput.value = "";
      hidePreview();
      uploading = null;
      setError("");
      updateSummary();
    },
  };
}
