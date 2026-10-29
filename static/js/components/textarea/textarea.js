// Textarea component: live character counter, and Ctrl/Cmd + Enter to send the form.
(function () {
  const WARN_AT = 0.9;

  function updateCounter(textarea) {
    const counter = document.querySelector(
      `[data-char-counter="${CSS.escape(textarea.id)}"]`,
    );
    if (!counter) return;

    const max = Number(counter.dataset.max) || textarea.maxLength;
    const length = textarea.value.length;
    counter.textContent = `${length}/${max}`;

    const near = length >= max * WARN_AT;
    counter.classList.toggle("text-tertiary-700", near);
    counter.classList.toggle("font-semibold", near);
    counter.classList.toggle("text-neutral-800", !near);
  }

  function initTextareas() {
    if (window.__textareaInitialized) return;
    window.__textareaInitialized = true;

    document.addEventListener("input", (event) => {
      const textarea = event.target.closest?.("[data-textarea] textarea");
      if (textarea) updateCounter(textarea);
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Enter" || !(event.ctrlKey || event.metaKey)) return;
      const textarea = event.target.closest?.("[data-textarea] textarea");
      if (!textarea?.form) return;
      event.preventDefault();
      textarea.form.requestSubmit();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initTextareas);
  } else {
    initTextareas();
  }
})();
