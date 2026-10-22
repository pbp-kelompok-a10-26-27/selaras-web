(function () {
  function getToastContainer() {
    let container = document.getElementById("toast-container");
    if (!container) {
      container = document.createElement("div");
      container.id = "toast-container";
      container.className =
        "fixed md:top-4 md:right-4 top-6 right-0 z-50 flex flex-col gap-3 pointer-events-none max-w-md w-full px-4 sm:px-0";
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

  window.showToast = function (options = {}) {
    const {
      type = "success",
      title = "",
      message = "",
      duration = 4000,
    } = options;

    const container = getToastContainer();
    const toast = document.createElement("div");

    const colorClasses = getTypeClasses(type);

    toast.className = `toast-item pointer-events-auto flex items-start gap-3 w-full p-4 rounded-2xl shadow-xl transform translate-y-2 opacity-0 transition-all duration-300 ease-out ${colorClasses}`;
    toast.setAttribute("role", "alert");

    toast.innerHTML = `
            <div class="flex-shrink-0 mt-0.5">${getIconSvg(type)}</div>
            <div class="flex-1 min-w-0">
                ${title ? `<h4 class="font-sans md:text-s5 text-s6 text-foreground leading-tight truncate">${title}</h4>` : ""}
                <p class="font-sans md:text-b3 text-b4 text-foreground/80 mt-0.5 leading-normal">${message}</p>
            </div>
            <button type="button" class="toast-close flex-shrink-0 text-neutral-700 hover:text-foreground transition-colors p-1 rounded-lg hover:bg-neutral-200/60 cursor-pointer" aria-label="Close">
                <svg class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
        `;

    container.appendChild(toast);

    // Trigger smooth entrance animation
    requestAnimationFrame(() => {
      toast.classList.remove("translate-y-2", "opacity-0");
      toast.classList.add("translate-y-0", "opacity-100");
    });

    let dismissTimeout;

    function dismiss() {
      toast.classList.remove("translate-y-0", "opacity-100");
      toast.classList.add("translate-y-2", "opacity-0");
      setTimeout(() => {
        if (toast.parentElement) toast.remove();
      }, 300);
    }

    // Close button event
    toast.querySelector(".toast-close").addEventListener("click", dismiss);

    // Auto dismiss timer
    if (duration > 0) {
      dismissTimeout = setTimeout(dismiss, duration);

      // Pause timer on hover
      toast.addEventListener("mouseenter", () => clearTimeout(dismissTimeout));
      toast.addEventListener("mouseleave", () => {
        dismissTimeout = setTimeout(dismiss, 2000);
      });
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
