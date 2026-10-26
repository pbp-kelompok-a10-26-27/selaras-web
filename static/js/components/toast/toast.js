(function () {
  // Older toasts are removed beyond this, so they never cover a small screen
  const MAX_VISIBLE = 3;
  const EXIT_MS = 300;

  // Mobile & tablet: top of the screen, full width with a 16px gutter (and
  // clear of the notch). Desktop (lg): bottom-right corner, fixed width.
  // flex-col-reverse on top / flex-col at the bottom keeps the newest toast
  // closest to the edge it slides in from.
  function getToastContainer() {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className =
        "pointer-events-none fixed inset-x-0 top-[max(1rem,env(safe-area-inset-top))] z-[60] mx-auto flex w-full max-w-md flex-col-reverse gap-2 px-4 sm:gap-3 lg:inset-x-auto lg:top-auto lg:right-6 lg:bottom-6 lg:mx-0 lg:w-96 lg:max-w-none lg:flex-col lg:px-0";
      document.body.appendChild(container);
    }
    return container;
  }

  // SVG Icon helper string matching Lucide designs
  function getIconSvg(type) {
    switch (type) {
      case "error":
        return '<svg class="w-5 h-5 text-red-100" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>';
      case "warning":
        return '<svg class="w-5 h-5 text-yellow-200" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>';
      case "info":
        return '<svg class="w-5 h-5 text-blue-200" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>';
      case "success":
      default:
        return '<svg class="w-5 h-5 text-primary-600" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>';
    }
  }

  // Helper to map type to Tailwind classes (avoiding purge issues)
  function getTypeClasses(type) {
    switch (type) {
      case "error":
        return "border border-red-100 bg-neutral-100";
      case "warning":
        return "border border-yellow-200 bg-neutral-100";
      case "info":
        return "border border-blue-100 bg-neutral-100";
      case "success":
      default:
        return "border border-primary-500 bg-neutral-100";
    }
  }

  // Hidden state slides toward the edge the toast comes from:
  // up on mobile/tablet (top), down on desktop (bottom-right)
  const HIDDEN_CLASSES = ["opacity-0", "-translate-y-3", "lg:translate-y-3"];
  const SHOWN_CLASSES = ["opacity-100", "translate-y-0", "lg:translate-y-0"];

  window.showToast = function (options = {}) {
    const {
      type = "success",
      title = "",
      message = "",
      duration = 4000,
    } = options;

    const container = getToastContainer();
    const toast = document.createElement("div");

    toast.className = `toast-item pointer-events-auto flex w-full items-start gap-3 rounded-2xl p-3 shadow-xl transition-all duration-300 ease-out motion-reduce:transition-none sm:p-4 ${HIDDEN_CLASSES.join(" ")} ${getTypeClasses(type)}`;
    // Errors interrupt screen readers; other toasts wait for a pause
    toast.setAttribute("role", type === "error" ? "alert" : "status");

    // Only fixed markup goes through innerHTML; title and message are set
    // with textContent below, so user content (e.g. a ticket subject) can
    // never be run as HTML
    toast.innerHTML = `
            <div class="flex-shrink-0 mt-0.5">${getIconSvg(type)}</div>
            <div class="flex-1 min-w-0">
                <h4 class="toast-title line-clamp-2 font-sans text-s6 leading-tight text-foreground sm:text-s5"></h4>
                <p class="toast-message mt-0.5 break-words font-sans text-b4 leading-normal text-foreground/80 sm:text-sm"></p>
            </div>
            <button type="button" class="toast-close -m-1.5 flex h-9 w-9 flex-shrink-0 cursor-pointer items-center justify-center rounded-lg text-neutral-700 transition-colors hover:bg-neutral-200/60 hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary-500" aria-label="Close notification">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24" aria-hidden="true"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        `;

    const titleEl = toast.querySelector(".toast-title");
    if (title) titleEl.textContent = title;
    else titleEl.remove();
    toast.querySelector(".toast-message").textContent = message;

    container.appendChild(toast);

    // Drop the oldest toasts beyond the limit
    const visible = container.querySelectorAll(".toast-item:not([data-leaving])");
    [...visible].slice(0, Math.max(0, visible.length - MAX_VISIBLE)).forEach((old) => old._dismiss?.());

    // Trigger smooth entrance animation
    requestAnimationFrame(() => {
      toast.classList.remove(...HIDDEN_CLASSES);
      toast.classList.add(...SHOWN_CLASSES);
    });

    let dismissTimeout;

    function dismiss() {
      if (toast.dataset.leaving) return;
      toast.dataset.leaving = "true";
      clearTimeout(dismissTimeout);
      toast.classList.remove(...SHOWN_CLASSES);
      toast.classList.add(...HIDDEN_CLASSES);
      setTimeout(() => {
        if (toast.parentElement) toast.remove();
      }, EXIT_MS);
    }
    toast._dismiss = dismiss;

    // Close button event
    toast.querySelector(".toast-close").addEventListener("click", dismiss);

    // Auto dismiss timer, paused while the user hovers or focuses the toast
    if (duration > 0) {
      dismissTimeout = setTimeout(dismiss, duration);

      const pause = () => clearTimeout(dismissTimeout);
      const resume = () => {
        if (toast.matches(":hover, :focus-within")) return;
        clearTimeout(dismissTimeout);
        dismissTimeout = setTimeout(dismiss, 2000);
      };
      toast.addEventListener("mouseenter", pause);
      toast.addEventListener("focusin", pause);
      toast.addEventListener("mouseleave", resume);
      toast.addEventListener("focusout", () => setTimeout(resume));
    }
  };
})();

// Optional Preview Button Event Bindings (Safe if buttons are missing)
document.addEventListener("DOMContentLoaded", () => {
  const bindClick = (id, type, title, message) => {
    const btn = document.getElementById(id);
    if (btn) {
      btn.addEventListener("click", () => {
        showToast({ type, title, message, duration: 4000 });
      });
    }
  };

  bindClick(
    "toast-preview-1",
    "success",
    "Success!",
    "This is a success toast notification.",
  );
  bindClick(
    "toast-preview-2",
    "error",
    "Error!",
    "This is an error toast notification.",
  );
  bindClick(
    "toast-preview-3",
    "warning",
    "Warning!",
    "This is a warning toast notification.",
  );
  bindClick(
    "toast-preview-4",
    "info",
    "Info!",
    "This is an info toast notification.",
  );
});
