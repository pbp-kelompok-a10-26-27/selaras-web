(function () {
  if (window.__tooltipInitialized) return;
  window.__tooltipInitialized = true;

  // Matches the bubble's `duration-200` fade
  const FADE_MS = 200;

  function isShownByUser(wrapper) {
    return wrapper.matches(":hover") || wrapper.querySelector(":focus-visible");
  }

  // Briefly shows feedback text (e.g. "Copied!") in a tooltip, then fades it
  // out and only restores the original text once it's invisible, so the
  // swap back never flickers in front of the user.
  window.flashTooltip = function (wrapper, text, duration = 1500) {
    const content = wrapper?.querySelector("[data-tooltip-content]");
    if (!content) return;

    content.dataset.defaultText ??= content.textContent.trim();
    clearTimeout(wrapper._tooltipHideTimer);
    clearTimeout(wrapper._tooltipRestoreTimer);

    content.textContent = text;
    wrapper.removeAttribute("data-tooltip-dismissed");
    wrapper.setAttribute("data-tooltip-open", "");

    wrapper._tooltipHideTimer = setTimeout(() => {
      wrapper.removeAttribute("data-tooltip-open");
      const restore = () => {
        content.textContent = content.dataset.defaultText;
      };
      // Still hovered/focused: the tooltip stays visible, so swap right away
      if (isShownByUser(wrapper)) restore();
      else wrapper._tooltipRestoreTimer = setTimeout(restore, FADE_MS);
    }, duration);
  };

  // Escape hides any visible tooltip without moving focus (WCAG 1.4.13)
  document.addEventListener("keydown", (event) => {
    if (event.key !== "Escape") return;

    document.querySelectorAll("[data-tooltip-wrapper]").forEach((wrapper) => {
      if (isShownByUser(wrapper) || wrapper.hasAttribute("data-tooltip-open")) {
        wrapper.removeAttribute("data-tooltip-open");
        wrapper.setAttribute("data-tooltip-dismissed", "");
      }
    });
  });

  // A dismissed tooltip works again once the pointer or focus has left it
  function rearm(event) {
    const wrapper = event.target.closest?.("[data-tooltip-wrapper]");
    if (wrapper && !wrapper.contains(event.relatedTarget)) {
      wrapper.removeAttribute("data-tooltip-dismissed");
    }
  }
  document.addEventListener("mouseout", rearm);
  document.addEventListener("focusout", rearm);
})();
