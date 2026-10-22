(function () {
  window.toggleSkeleton = function (targetId, show = true) {
    const el = document.getElementById(targetId);
    if (!el) return;

    if (show) {
      el.classList.remove("hidden");
    } else {
      el.classList.add("hidden");
    }
  };

  // Optional: Auto-bind with HTMX events if desired
  document.addEventListener("htmx:beforeRequest", (e) => {
    const target = e.detail.target;
    if (target && target.hasAttribute("data-skeleton-target")) {
      const skeletonId = target.getAttribute("data-skeleton-target");
      window.toggleSkeleton(skeletonId, true);
    }
  });

  document.addEventListener("htmx:afterSwap", (e) => {
    const target = e.detail.target;
    if (target && target.hasAttribute("data-skeleton-target")) {
      const skeletonId = target.getAttribute("data-skeleton-target");
      window.toggleSkeleton(skeletonId, false);
    }
  });
})();
