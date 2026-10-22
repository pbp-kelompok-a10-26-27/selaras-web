(function () {
  function initModalSystem() {
    if (window.__modalInitialized) return;
    window.__modalInitialized = true;

    window.openModal = function (modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) {
        console.warn(`Modal with ID "${modalId}" not found.`);
        return;
      }

      const dialog = modal.querySelector(".modal-dialog");

      // Show backdrop
      modal.classList.remove("opacity-0", "pointer-events-none");
      modal.classList.add("opacity-100", "pointer-events-auto");

      // Prevent body background scroll
      document.body.style.overflow = "hidden";

      // Animate dialog entrance
      requestAnimationFrame(() => {
        if (dialog) {
          dialog.classList.remove("scale-95", "translate-y-4", "opacity-0");
          dialog.classList.add("scale-100", "translate-y-0", "opacity-100");
        }
      });

      // Focus first focusable element for accessibility
      setTimeout(() => {
        const focusable = modal.querySelectorAll(
          'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])',
        );
        if (focusable.length) focusable[0].focus();
      }, 100);
    };

    window.closeModal = function (modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) return;

      const dialog = modal.querySelector(".modal-dialog");

      // Animate dialog exit
      if (dialog) {
        dialog.classList.remove("scale-100", "translate-y-0", "opacity-100");
        dialog.classList.add("scale-95", "translate-y-4", "opacity-0");
      }

      // Fade out backdrop
      modal.classList.remove("opacity-100", "pointer-events-auto");
      modal.classList.add("opacity-0", "pointer-events-none");

      // Restore body scroll
      document.body.style.overflow = "";
    };

    // Event Delegation for triggers and close buttons
    document.addEventListener("click", (e) => {
      const openBtn = e.target.closest("[data-modal-open]");
      if (openBtn) {
        e.preventDefault();
        const targetId = openBtn.getAttribute("data-modal-open");
        window.openModal(targetId);
        return;
      }

      const closeBtn = e.target.closest("[data-modal-close], .modal-close");
      if (closeBtn) {
        e.preventDefault();
        const modal = closeBtn.closest(".modal-backdrop");
        if (modal) window.closeModal(modal.id);
        return;
      }

      // Close on backdrop click
      if (e.target.classList.contains("modal-backdrop")) {
        window.closeModal(e.target.id);
      }
    });

    // Close on Escape key
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        const openModals = document.querySelectorAll(
          ".modal-backdrop:not(.pointer-events-none)",
        );
        openModals.forEach((modal) => window.closeModal(modal.id));
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initModalSystem);
  } else {
    initModalSystem();
  }
})();
