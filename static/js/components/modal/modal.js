(function () {
  const FOCUSABLE =
    'button:not([disabled]), [href], input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function getFocusable(modal) {
    return [...modal.querySelectorAll(FOCUSABLE)].filter(
      (el) => el.getClientRects().length > 0,
    );
  }

  function initModalSystem() {
    if (window.__modalInitialized) return;
    window.__modalInitialized = true;

    // A closed modal is only invisible, so make it inert: otherwise keyboard
    // users can Tab into its hidden fields and screen readers read it out
    document.querySelectorAll(".modal-backdrop").forEach((modal) => {
      modal.inert = true;
    });

    window.openModal = function (modalId) {
      const modal = document.getElementById(modalId);
      if (!modal) {
        console.warn(`Modal with ID "${modalId}" not found.`);
        return;
      }

      const dialog = modal.querySelector(".modal-dialog");

      // Remember what opened the modal, to return focus there on close
      modal._returnFocusTo = document.activeElement;
      modal.inert = false;

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

      // Focus the element marked [data-modal-autofocus], else the first focusable one
      setTimeout(() => {
        const target =
          modal.querySelector("[data-modal-autofocus]") ?? getFocusable(modal)[0];
        target?.focus();
      }, 100);

      modal.dispatchEvent(new CustomEvent("modal:open", { bubbles: true }));
    };

    window.closeModal = function (modalId) {
      const modal = document.getElementById(modalId);
      if (!modal || modal.inert) return;

      const dialog = modal.querySelector(".modal-dialog");

      // Animate dialog exit
      if (dialog) {
        dialog.classList.remove("scale-100", "translate-y-0", "opacity-100");
        dialog.classList.add("scale-95", "translate-y-4", "opacity-0");
      }

      // Fade out backdrop
      modal.classList.remove("opacity-100", "pointer-events-auto");
      modal.classList.add("opacity-0", "pointer-events-none");
      modal.inert = true;

      // Restore body scroll
      document.body.style.overflow = "";

      // Put keyboard focus back where the user was
      modal._returnFocusTo?.focus?.();
      modal._returnFocusTo = null;

      modal.dispatchEvent(new CustomEvent("modal:close", { bubbles: true }));
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

    document.addEventListener("keydown", (e) => {
      const openModal = document.querySelector(
        ".modal-backdrop:not(.pointer-events-none)",
      );
      if (!openModal) return;

      // Close on Escape key
      if (e.key === "Escape") {
        window.closeModal(openModal.id);
        return;
      }

      // Keep Tab inside the open modal (focus trap)
      if (e.key === "Tab") {
        const focusable = getFocusable(openModal);
        if (!focusable.length) return;
        const first = focusable[0];
        const last = focusable[focusable.length - 1];

        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initModalSystem);
  } else {
    initModalSystem();
  }
})();
