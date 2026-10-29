(function () {
  function initDropdowns() {
    // Prevent multiple initializations
    if (window.__dropdownInitialized) return;
    window.__dropdownInitialized = true;

    // Global Event Delegation for all dropdowns
    document.addEventListener("click", (e) => {
      const trigger = e.target.closest(".dropdown-trigger");
      const item = e.target.closest(".dropdown-item");
      const wrapper = e.target.closest(".custom-dropdown");

      // 1. Handle Trigger Click (Open / Close)
      if (trigger) {
        const currentWrapper = trigger.closest(".custom-dropdown");
        const menu = currentWrapper.querySelector(".dropdown-menu");
        const arrow = currentWrapper.querySelector(".dropdown-arrow");
        const isOpen = trigger.getAttribute("aria-expanded") === "true";

        // Close all other open dropdowns first
        document.querySelectorAll(".custom-dropdown").forEach((w) => {
          if (w !== currentWrapper) {
            closeDropdown(w);
          }
        });

        if (isOpen) {
          closeDropdown(currentWrapper);
        } else {
          openDropdown(currentWrapper, trigger, menu, arrow);
        }
        return;
      }

      // 2. Handle Item Selection Click
      if (item) {
        const currentWrapper = item.closest(".custom-dropdown");
        const hiddenInput = currentWrapper.querySelector(
          'input[type="hidden"]',
        );
        const labelSpan = currentWrapper.querySelector(".dropdown-label");

        const val = item.getAttribute("data-value");
        const lbl = item.getAttribute("data-label");

        hiddenInput.value = val;
        labelSpan.textContent = lbl;
        labelSpan.classList.remove("text-foreground/80");

        // Dispatch change event for Django forms / HTMX
        hiddenInput.dispatchEvent(new Event("change", { bubbles: true }));

        closeDropdown(currentWrapper);
        return;
      }

      // 3. Handle Click Outside (Close all dropdowns)
      if (!wrapper) {
        document.querySelectorAll(".custom-dropdown").forEach((w) => {
          closeDropdown(w);
        });
      }
    });

    // Handle Keyboard Navigation (Escape key)
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") {
        document.querySelectorAll(".custom-dropdown").forEach((w) => {
          closeDropdown(w);
        });
      }
    });
  }

  // Safely initialize whether DOM is loading or already ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initDropdowns);
  } else {
    initDropdowns();
  }
})();

function openDropdown(wrapper, trigger, menu, arrow) {
  trigger.setAttribute("aria-expanded", "true");
  menu.classList.remove("hidden");

  requestAnimationFrame(() => {
    menu.classList.remove("opacity-0", "translate-y-2");
    menu.classList.add("opacity-100", "translate-y-0");
    if (arrow) arrow.classList.add("rotate-180");
  });
}

function closeDropdown(wrapper) {
  const trigger = wrapper.querySelector(".dropdown-trigger");
  const menu = wrapper.querySelector(".dropdown-menu");
  const arrow = wrapper.querySelector(".dropdown-arrow");

  if (!trigger || trigger.getAttribute("aria-expanded") === "false") return;

  trigger.setAttribute("aria-expanded", "false");
  menu.classList.remove("opacity-100", "translate-y-0");
  menu.classList.add("opacity-0", "translate-y-2");
  if (arrow) arrow.classList.remove("rotate-180");

  setTimeout(() => {
    if (trigger.getAttribute("aria-expanded") === "false") {
      menu.classList.add("hidden");
    }
  }, 200);
}
