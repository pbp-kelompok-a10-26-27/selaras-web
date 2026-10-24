(function () {
  const STORAGE_KEY = "dashboard-sidebar";
  const desktop = window.matchMedia("(min-width: 1024px)");
  const FOCUSABLE =
    'a[href], button:not([disabled]), input:not([disabled]), [tabindex]:not([tabindex="-1"])';

  function initSidebar() {
    const sidebar = document.querySelector("[data-sidebar]");
    if (!sidebar || sidebar.dataset.initialized) return;
    sidebar.dataset.initialized = "true";

    const root = document.documentElement;
    const openButton = document.querySelector("[data-sidebar-open]");
    const closeButton = sidebar.querySelector("[data-sidebar-close]");
    const toggleButton = sidebar.querySelector("[data-sidebar-toggle]");
    const backdrop = document.querySelector("[data-sidebar-backdrop]");

    /* ---------- Desktop: collapse to icons, remembered per browser ---------- */

    function setCollapsed(collapsed, { save = true } = {}) {
      if (collapsed) root.dataset.sidebarState = "collapsed";
      else delete root.dataset.sidebarState;

      const label = collapsed ? "Expand sidebar" : "Collapse sidebar";
      toggleButton?.setAttribute("aria-expanded", String(!collapsed));
      toggleButton?.setAttribute("aria-label", label);
      toggleButton?.setAttribute("title", label);

      if (!save) return;
      try {
        localStorage.setItem(STORAGE_KEY, collapsed ? "collapsed" : "expanded");
      } catch {
        /* storage unavailable (private mode): the state just isn't remembered */
      }
    }

    toggleButton?.addEventListener("click", () => {
      setCollapsed(root.dataset.sidebarState !== "collapsed");
    });
    // The base template already applied the saved state before paint; sync the button
    setCollapsed(root.dataset.sidebarState === "collapsed", { save: false });

    /* ---------- Mobile & tablet: off-canvas drawer ---------- */

    let isOpen = false;

    // Off-screen, the drawer must not be reachable with Tab or a screen reader
    function syncInert() {
      sidebar.inert = !desktop.matches && !isOpen;
    }

    function openDrawer() {
      isOpen = true;
      sidebar.dataset.open = "";
      backdrop?.setAttribute("data-open", "");
      openButton?.setAttribute("aria-expanded", "true");
      document.body.style.overflow = "hidden";
      syncInert();

      const current = sidebar.querySelector('[aria-current="page"]');
      (current ?? sidebar.querySelector(FOCUSABLE))?.focus();
    }

    function closeDrawer({ returnFocus = true } = {}) {
      if (!isOpen) return;
      isOpen = false;
      delete sidebar.dataset.open;
      backdrop?.removeAttribute("data-open");
      openButton?.setAttribute("aria-expanded", "false");
      document.body.style.overflow = "";
      syncInert();
      if (returnFocus) openButton?.focus();
    }

    openButton?.addEventListener("click", openDrawer);
    closeButton?.addEventListener("click", () => closeDrawer());
    backdrop?.addEventListener("click", () => closeDrawer());

    // Following a link navigates away; close without stealing focus
    sidebar.addEventListener("click", (event) => {
      if (isOpen && event.target.closest("[data-sidebar-link]")) {
        closeDrawer({ returnFocus: false });
      }
    });

    document.addEventListener("keydown", (event) => {
      if (!isOpen) return;

      if (event.key === "Escape") {
        closeDrawer();
        return;
      }

      // Keep Tab inside the open drawer
      if (event.key === "Tab") {
        const focusable = [...sidebar.querySelectorAll(FOCUSABLE)].filter(
          (el) => el.getClientRects().length > 0,
        );
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
    });

    // Rotating a tablet into desktop width while the drawer is open
    desktop.addEventListener("change", () => {
      if (desktop.matches) closeDrawer({ returnFocus: false });
      syncInert();
    });

    syncInert();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSidebar);
  } else {
    initSidebar();
  }
})();
