// Navbar notification bell: opens a popover with the latest notifications, keeps the
// unread count fresh while the tab is visible, and shows a toast the first time a new
// badge notification arrives. Without JavaScript the bell is a link to the full list.
import { renderRelativeTimes } from "../relative-time/relative-time.js";

const POLL_MS = 60_000;
const TOASTED_KEY = "selaras:toasted-notifications";

function readToasted() {
  try {
    return new Set(JSON.parse(localStorage.getItem(TOASTED_KEY) || "[]"));
  } catch {
    return new Set();
  }
}

function saveToasted(ids) {
  try {
    localStorage.setItem(TOASTED_KEY, JSON.stringify([...ids].slice(-50)));
  } catch {
    // Storage can be blocked; the toast may then show again on the next page
  }
}

function initBell(root) {
  const bell = root.querySelector("[data-bell]");
  const count = root.querySelector("[data-bell-count]");
  const navbar = root.closest("[data-navbar]");
  const panel = navbar?.querySelector("[data-bell-panel]");
  const body = panel?.querySelector("[data-bell-body]");
  const readAll = panel?.querySelector("[data-bell-read-all]");
  if (!bell || !panel || !body) return;

  let unread = Number.parseInt(count.textContent, 10) || 0;
  let loading = null;

  function paintCount(value) {
    const grew = value > unread;
    unread = value;
    count.textContent = value > 99 ? "99+" : String(value);
    count.classList.toggle("hidden", value === 0);
    bell.setAttribute(
      "aria-label",
      value ? `Notifikasi, ${value} belum dibaca` : "Notifikasi",
    );
    if (readAll) readAll.disabled = value === 0;
    if (grew) {
      bell.dataset.ringing = "";
      setTimeout(() => delete bell.dataset.ringing, 900);
    }
  }

  function toastNewBadges(container) {
    const toasted = readToasted();
    let changed = false;
    container
      .querySelectorAll('[data-notification][data-unread][data-kind="badge_earned"]')
      .forEach((item) => {
        if (toasted.has(item.dataset.id)) return;
        toasted.add(item.dataset.id);
        changed = true;
        const title = item.querySelector("[data-notification-title]")?.textContent?.trim();
        window.showToast?.({
          type: "success",
          title: title || "Lencana baru!",
          message: "Buka profil untuk memasang lencana di samping namamu.",
        });
      });
    if (changed) saveToasted(toasted);
  }

  async function refresh() {
    if (loading) return loading;
    loading = fetch(root.dataset.feedUrl, {
      headers: { Accept: "application/json" },
      credentials: "same-origin",
    })
      .then((response) => (response.ok ? response.json() : Promise.reject(response)))
      .then((data) => {
        body.innerHTML = data.html;
        renderRelativeTimes(body);
        paintCount(data.unread);
        toastNewBadges(body);
      })
      .catch(() => {
        if (!body.querySelector("[data-notification]")) {
          body.innerHTML =
            '<p class="px-4 py-8 text-center font-sans text-sm text-neutral-800">Notifikasi belum dapat dimuat. Coba lagi sebentar lagi.</p>';
        }
      })
      .finally(() => {
        loading = null;
      });
    return loading;
  }

  const isOpen = () => panel.dataset.open === "true";

  function open() {
    panel.dataset.open = "true";
    bell.setAttribute("aria-expanded", "true");
    refresh();
  }

  function close({ focusBell = false } = {}) {
    if (!isOpen()) return;
    panel.dataset.open = "false";
    bell.setAttribute("aria-expanded", "false");
    if (focusBell) bell.focus();
  }

  panel.inert = true;
  new MutationObserver(() => {
    panel.inert = !isOpen();
  }).observe(panel, { attributes: true, attributeFilter: ["data-open"] });

  bell.addEventListener("click", (event) => {
    // Ctrl/Cmd-click still opens the full page in a new tab
    if (event.metaKey || event.ctrlKey || event.shiftKey) return;
    event.preventDefault();
    if (isOpen()) close();
    else open();
  });

  document.addEventListener("click", (event) => {
    if (isOpen() && !panel.contains(event.target) && !bell.contains(event.target)) {
      close();
    }
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && isOpen()) close({ focusBell: true });
  });

  readAll?.addEventListener("click", async () => {
    readAll.disabled = true;
    const response = await fetch(root.dataset.readAllUrl, {
      method: "POST",
      headers: { "X-CSRFToken": root.dataset.csrf, Accept: "application/json" },
      credentials: "same-origin",
    }).catch(() => null);
    if (response?.ok) {
      paintCount(0);
      body.querySelectorAll("[data-unread]").forEach((item) => {
        item.removeAttribute("data-unread");
        item.classList.remove("bg-primary-50");
        item.querySelector('[aria-label="Belum dibaca"]')?.remove();
      });
    } else {
      readAll.disabled = false;
      window.showToast?.({
        type: "error",
        title: "Gagal",
        message: "Notifikasi belum dapat ditandai dibaca.",
      });
    }
  });

  // Poll only while the tab is visible; check right away when it comes back
  setInterval(() => {
    if (document.visibilityState === "visible") refresh();
  }, POLL_MS);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible") refresh();
  });

  // Something unread on load may be a brand-new badge worth celebrating
  if (unread > 0) refresh();
}

document.querySelectorAll("[data-bell-root]").forEach(initBell);
