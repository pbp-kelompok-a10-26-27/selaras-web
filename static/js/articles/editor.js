// Article editor: live card preview, word count / reading time, unsaved-changes guard and
// submit loading. The server validates everything; this only gives feedback while typing.
import { setButtonLoading, showMessagesAsToasts } from "../accounts/shared.js";

const form = document.querySelector("[data-article-form]");

if (form) {
  init(form);
}

function words(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

function init(root) {
  const preview = document.querySelector("[data-preview-card]");
  const title = root.querySelector('[data-preview-source="title"]');
  const summary = root.querySelector('[data-preview-source="summary"]');
  const content = root.querySelector('[data-preview-source="content"]');
  const fileInput = root.querySelector('input[type="file"]');
  const clearBox = root.querySelector("[data-image-clear]");
  const wordCount = root.querySelector("[data-word-count]");
  const readingTime = root.querySelector("[data-reading-time]");
  const dirtyDot = root.querySelector("[data-dirty-dot]");
  const dirtyLabel = root.querySelector("[data-dirty-label]");

  const previewTitle = preview.querySelector("[data-preview-title]");
  const previewSummary = preview.querySelector("[data-preview-summary]");
  const previewCategory = preview.querySelector("[data-preview-category]");
  const previewMinutes = preview.querySelector("[data-preview-minutes]");
  const previewImage = preview.querySelector("[data-preview-image]");
  const previewPlaceholder = preview.querySelector("[data-preview-placeholder]");
  const originalImage = previewImage.getAttribute("src") || "";
  let objectUrl = null;
  let dirty = false;
  let submitting = false;

  showMessagesAsToasts();

  const fill = (node, value) => {
    node.textContent = value.trim() || node.dataset.empty;
  };

  function updateText() {
    fill(previewTitle, title.value);
    fill(previewSummary, summary.value);
    const count = words(content.value);
    const minutes = `${Math.max(Math.round(count / 200), 1)} menit baca`;
    wordCount.textContent = `${count.toLocaleString("id-ID")} kata`;
    readingTime.textContent = minutes;
    previewMinutes.textContent = minutes;
  }

  function showImage(src) {
    previewImage.hidden = false;
    previewImage.classList.toggle("hidden", !src);
    previewPlaceholder.classList.toggle("hidden", Boolean(src));
    if (src) previewImage.src = src;
  }

  function updateImage() {
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = null;
    const file = fileInput?.files[0];
    if (file && file.type.startsWith("image/")) {
      objectUrl = URL.createObjectURL(file);
      showImage(objectUrl);
    } else {
      showImage(clearBox?.checked ? "" : originalImage);
    }
  }

  function markDirty() {
    if (dirty) return;
    dirty = true;
    dirtyDot.dataset.dirty = "true";
    dirtyLabel.textContent = "Ada perubahan yang belum disimpan";
  }

  [title, summary, content].forEach((field) =>
    field.addEventListener("input", () => {
      updateText();
      markDirty();
    }),
  );

  // The dropdown component fires "change" on its hidden input
  root.addEventListener("change", (event) => {
    markDirty();
    if (event.target.matches?.('input[type="hidden"][name="category"]')) {
      const label = event.target.closest(".custom-dropdown")?.querySelector(".dropdown-label");
      if (label) previewCategory.textContent = label.textContent.trim();
    }
    if (event.target === fileInput || event.target === clearBox) updateImage();
  });

  // file-drop.js clears the input with its own button, without a change event
  root.querySelector("[data-file-clear]")?.addEventListener("click", () =>
    setTimeout(updateImage, 0),
  );

  root.addEventListener("submit", (event) => {
    submitting = true;
    const submit = event.submitter;
    // Disabling right now would drop the submitter's name/value; wait a tick
    setTimeout(() => setButtonLoading(submit, true), 0);
  });

  window.addEventListener("beforeunload", (event) => {
    if (!dirty || submitting) return;
    event.preventDefault();
  });

  // Deleting from the modal is intentional; don't ask about unsaved changes
  document.querySelector("form[data-skip-dirty]")?.addEventListener("submit", () => {
    submitting = true;
  });

  updateText();
}
