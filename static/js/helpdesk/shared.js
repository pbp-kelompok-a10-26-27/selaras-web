// Code shared by the helpdesk pages (stats.js and ticket_detail.js).
// Keeping it in one place means a status, priority or avatar looks the
// same on every page, and a fix only has to be made once.

// Classes are written out in full so Tailwind can detect them at build time
export const TICKET_STATUS_CONFIG = {
  open: {
    icon: "circle-dot",
    accent: "bg-orange-100",
    chip: "border-orange-100/50 bg-orange-100/15",
    iconColor: "text-orange-100",
  },
  in_progress: {
    icon: "loader",
    accent: "bg-yellow-200",
    chip: "border-yellow-200/70 bg-yellow-100/40",
    iconColor: "text-secondary-700",
  },
  resolved: {
    icon: "circle-check",
    accent: "bg-primary-500",
    chip: "border-primary-500/50 bg-primary-200",
    iconColor: "text-primary-700",
  },
  closed: {
    icon: "lock",
    accent: "bg-secondary-100",
    chip: "border-secondary-200 bg-secondary-100",
    iconColor: "text-secondary-500",
  },
};

export const TICKET_PRIORITY_CONFIG = {
  low: {
    icon: "arrow-down",
    accent: "bg-primary-300",
    chip: "border-primary-300/60 bg-primary-100",
    iconColor: "text-primary-700",
  },
  normal: {
    icon: "equal",
    accent: "bg-blue-100",
    chip: "border-blue-100/40 bg-blue-100/10",
    iconColor: "text-blue-200",
  },
  high: {
    icon: "arrow-up",
    accent: "bg-red-100",
    chip: "border-red-100/40 bg-red-100/10",
    iconColor: "text-red-100",
  },
};

const AVATAR_COLORS = [
  "bg-primary-200 text-primary-900",
  "bg-secondary-200 text-secondary-900",
  "bg-tertiary-300 text-tertiary-900",
  "bg-yellow-100 text-secondary-800",
];

/* ================================ TIME ================================ */

const relativeTimeFormatter = new Intl.RelativeTimeFormat("id", {
  numeric: "auto",
});
const absoluteTimeFormatter = new Intl.DateTimeFormat("id", {
  dateStyle: "medium",
  timeStyle: "short",
});

const RELATIVE_TIME_UNITS = [
  ["year", 60 * 60 * 24 * 365],
  ["month", 60 * 60 * 24 * 30],
  ["week", 60 * 60 * 24 * 7],
  ["day", 60 * 60 * 24],
  ["hour", 60 * 60],
  ["minute", 60],
];

export function formatRelativeTime(date) {
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);

  for (const [unit, unitSeconds] of RELATIVE_TIME_UNITS) {
    if (Math.abs(seconds) >= unitSeconds) {
      return relativeTimeFormatter.format(
        Math.round(seconds / unitSeconds),
        unit,
      );
    }
  }
  return "baru saja";
}

/* ================================ DOM ================================= */

// Small helper to keep the element factories readable
export function el(tag, className = "", text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

export function createIcon(name, className = "w-4 h-4") {
  const icon = el("i", className);
  icon.setAttribute("data-lucide", name);
  icon.setAttribute("aria-hidden", "true");
  return icon;
}

const toPascalCase = (name) => name.replace(/(^|-)(\w)/g, (_, __, letter) => letter.toUpperCase());

// Swaps the <i data-lucide> placeholders inside `root` for SVGs. Done by hand
// because lucide.createIcons() (0.469 UMD) ignores `root` and only scans
// `document`, so elements not yet on the page (like a freshly built pager) were skipped.
export function renderLucideIcons(root = document) {
  const lucide = window.lucide;
  if (!lucide) {
    console.warn("Lucide is not loaded. Icons will not be rendered.");
    return;
  }

  root.querySelectorAll("[data-lucide]:not(svg)").forEach((placeholder) => {
    const name = placeholder.getAttribute("data-lucide");
    const iconNode = lucide.icons[toPascalCase(name)];
    if (!iconNode) {
      console.warn(`Lucide icon "${name}" not found.`);
      return;
    }

    const svg = lucide.createElement(iconNode);
    // Keep the placeholder's attributes (aria-hidden, data-*, …) and add its classes
    for (const { name: attr, value } of placeholder.attributes) {
      if (attr !== "class") svg.setAttribute(attr, value);
    }
    svg.setAttribute("class", `lucide lucide-${name} ${placeholder.getAttribute("class") ?? ""}`.trim());
    placeholder.replaceWith(svg);
  });
}

// Relative time shown, exact date on hover
export function createTimeElement(isoString, prefix = "") {
  const time = el("time");
  if (!isoString) {
    time.textContent = `${prefix}—`;
    return time;
  }

  const date = new Date(isoString);
  time.dateTime = isoString;
  time.title = absoluteTimeFormatter.format(date);
  time.textContent = `${prefix}${formatRelativeTime(date)}`;
  return time;
}

// Non-interactive chip, visually matching the chips design-system component
export function createChipElement(label, config) {
  const chip = el(
    "span",
    `inline-flex shrink-0 items-center gap-1.5 rounded-full border px-2.5 py-1 font-sans text-xs font-semibold text-foreground ${config.chip}`,
  );
  chip.append(
    createIcon(config.icon, `w-3.5 h-3.5 ${config.iconColor}`),
    el("span", "", label),
  );
  return chip;
}

/* ===================== DESIGN SYSTEM COMPONENTS ======================= */
// Components are rendered by Django into <template> tags
// (templates/helpdesk/_component_templates.html); these helpers clone them.

// First element of a <template>, e.g. a single button
export function cloneTemplate(id) {
  const template = document.getElementById(id);
  if (!template) throw new Error(`Missing <template id="${id}">`);
  return template.content.firstElementChild.cloneNode(true);
}

// Everything inside a <template>, e.g. a multi-part skeleton
export function cloneTemplateContent(id) {
  const template = document.getElementById(id);
  if (!template) throw new Error(`Missing <template id="${id}">`);
  return template.content.cloneNode(true);
}

export function setButtonText(button, text) {
  button.querySelector("[data-button-text]").textContent = text;
}

// Shows the button component's spinner instead of its icon while busy
export function setButtonLoading(button, isLoading, loadingText) {
  const textNode = button.querySelector("[data-button-text]");
  if (isLoading) {
    button.dataset.idleText ??= textNode.textContent;
    if (loadingText) textNode.textContent = loadingText;
  } else if (button.dataset.idleText) {
    textNode.textContent = button.dataset.idleText;
    // Forget it, so the next loading state captures the text as it is then
    delete button.dataset.idleText;
  }

  button.setAttribute("aria-busy", String(isLoading));
  // The icon spans already have `inline-flex`, which a `hidden` class would
  // fight with; the hidden attribute always wins (Tailwind's preflight)
  button
    .querySelectorAll("[data-button-icon-left], [data-button-icon-right]")
    .forEach((icon) => (icon.hidden = isLoading));
  const spinner = button.querySelector("[data-button-spinner]");
  spinner.classList.toggle("hidden", !isLoading);
  spinner.classList.toggle("inline-flex", isLoading);
}

// Copy-to-clipboard ticket ID, built from the tooltip + button components
export function createTicketIdElement(ticketId) {
  const shortId = `#${ticketId.slice(0, 8).toUpperCase()}`;
  const wrapper = cloneTemplate("tpl-ticket-id");
  const button = wrapper.querySelector("button");
  const tooltip = wrapper.querySelector('[role="tooltip"]');

  // Each clone needs its own id, or every button would describe the same tooltip
  // (the component puts aria-describedby on its trigger wrapper; it belongs on the button)
  tooltip.id = `ticket-id-tooltip-${ticketId}`;
  wrapper.querySelector("[aria-describedby]")?.removeAttribute("aria-describedby");
  button.setAttribute("aria-describedby", tooltip.id);

  setButtonText(button, shortId);
  button.setAttribute("aria-label", `Salin ID tiket ${shortId}`);

  button.addEventListener("click", async (event) => {
    // Ticket cards are clickable; copying shouldn't open the ticket
    event.stopPropagation();

    try {
      await copyToClipboard(ticketId);
      // flashTooltip (components/tooltip/tooltip.js) shows the feedback, then
      // restores "Copy ticket ID" once the tooltip has faded out
      window.flashTooltip?.(wrapper, "Tersalin!");
      window.showToast?.({
        type: "success",
        title: "ID tiket tersalin",
        message: `${shortId} sudah ada di clipboard.`,
        duration: 2500,
      });
    } catch {
      window.flashTooltip?.(wrapper, "Gagal menyalin");
      window.showToast?.({
        type: "error",
        title: "ID tiket gagal disalin",
        message: "Browser kamu memblokir akses clipboard.",
      });
    }
  });

  return wrapper;
}

/* ============================== PAGINATION ============================== */

// Which page numbers to show: first, last and the current one ±1, with "…"
// for the gaps (a gap of exactly one page shows that page instead).
function getPageItems(page, totalPages) {
  const pages = [...new Set([1, page - 1, page, page + 1, totalPages])]
    .filter((p) => p >= 1 && p <= totalPages)
    .sort((a, b) => a - b);

  const items = [];
  pages.forEach((p, i) => {
    const gap = i ? p - pages[i - 1] : 0;
    if (gap === 2) items.push(p - 1);
    else if (gap > 2) items.push("gap");
    items.push(p);
  });
  return items;
}

/**
 * Numbered pager. Links carry real ?page= URLs (Ctrl/middle-click opens a new
 * tab); a plain click calls onChange(page) instead of reloading.
 * Phones show "Previous · Page 2 of 5 · Next"; wider screens show the numbers.
 */
export function createPagination({ page, totalPages, label, hrefFor, onChange }) {
  const nav = el("nav", "flex items-center justify-between gap-2 pt-2 pb-8 sm:justify-center");
  nav.setAttribute("aria-label", label);
  if (totalPages <= 1) {
    nav.hidden = true;
    return nav;
  }

  const base =
    "inline-flex min-h-10 min-w-10 items-center justify-center gap-1.5 rounded-xl border px-3 font-sans text-sm font-semibold tabular-nums outline-none transition-all duration-200 focus-visible:ring-2 focus-visible:ring-primary-500 focus-visible:ring-offset-1";

  const link = (target, className) => {
    const a = el("a", `${base} ${className}`);
    a.href = hrefFor(target);
    a.addEventListener("click", (event) => {
      if (event.ctrlKey || event.metaKey || event.shiftKey || event.button !== 0) return;
      event.preventDefault();
      onChange(target);
    });
    return a;
  };

  const step = (target, text, icon, disabled) => {
    if (disabled) {
      const span = el("span", `${base} cursor-not-allowed border-neutral-400 text-neutral-700 opacity-50`);
      span.setAttribute("aria-disabled", "true");
      span.append(createIcon(icon, "w-4 h-4"), el("span", "sr-only sm:not-sr-only", text));
      if (icon === "chevron-right") span.append(span.firstChild);
      return span;
    }
    const a = link(target, "border-neutral-400 bg-neutral-50 text-secondary-800 hover:border-neutral-500 hover:bg-neutral-300 active:scale-[0.97]");
    a.setAttribute("aria-label", `${text} page`);
    a.append(createIcon(icon, "w-4 h-4"), el("span", "sr-only sm:not-sr-only", text));
    if (icon === "chevron-right") a.append(a.firstChild); // icon after the text
    return a;
  };

  const numbers = el("ol", "hidden items-center gap-1 sm:flex");
  getPageItems(page, totalPages).forEach((item) => {
    const li = el("li");
    if (item === "gap") {
      li.append(el("span", "inline-flex min-w-6 justify-center font-sans text-sm text-neutral-800", "…"));
      li.setAttribute("aria-hidden", "true");
    } else if (item === page) {
      const current = el("span", `${base} border-secondary-700 bg-secondary-700 text-neutral-50 shadow-sm`, String(item));
      current.setAttribute("aria-current", "page");
      current.setAttribute("aria-label", `Halaman ${item}, halaman saat ini`);
      li.append(current);
    } else {
      const a = link(item, "border-transparent text-secondary-800 hover:border-neutral-400 hover:bg-neutral-300 active:scale-[0.97]");
      a.textContent = item;
      a.setAttribute("aria-label", `Page ${item}`);
      li.append(a);
    }
    numbers.append(li);
  });

  const compact = el("p", "font-sans text-sm text-neutral-900 sm:hidden");
  compact.append("Halaman ", el("strong", "font-semibold", String(page)), ` dari ${totalPages}`);

  nav.append(
    step(page - 1, "Sebelumnya", "chevron-left", page <= 1),
    compact,
    numbers,
    step(page + 1, "Berikutnya", "chevron-right", page >= totalPages),
  );
  renderLucideIcons(nav);
  return nav;
}

// "Menampilkan 11–20 dari 47" untuk data paginasi dari API
export function formatPageRange({ start, end, count }, noun = "tiket") {
  if (!count) return `0 ${noun}`;
  return start === 1 && end === count ? `${count} ${noun}` : `Menampilkan ${start}–${end} dari ${count} ${noun}`;
}

/* =============================== PEOPLE =============================== */

function getInitials(name) {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0].toUpperCase())
    .join("");
}

export function createAvatarElement(user, size = "h-10 w-10 text-sm") {
  if (!user) {
    const placeholder = el(
      "span",
      `flex shrink-0 items-center justify-center rounded-full border-2 border-dashed border-neutral-500 text-neutral-800 ${size}`,
    );
    placeholder.append(createIcon("user-round-x", "w-4 h-4"));
    return placeholder;
  }

  // Deterministic color so the same person always gets the same avatar
  const hash = [...user.name].reduce((sum, char) => sum + char.charCodeAt(0), 0);
  const colorClasses = AVATAR_COLORS[hash % AVATAR_COLORS.length];

  const avatar = el(
    "span",
    `flex shrink-0 select-none items-center justify-center rounded-full font-sans font-semibold ring-2 ring-neutral-50 ${size} ${colorClasses}`,
    getInitials(user.name),
  );
  avatar.setAttribute("aria-hidden", "true");
  return avatar;
}

export function createPersonElement(user, { caption, fallbackName, captionNode }) {
  const person = el("div", "flex min-w-0 flex-1 items-center gap-3");
  const text = el("div", "flex min-w-0 flex-col");

  const label = el(
    "span",
    "font-sans text-[0.6875rem] font-semibold uppercase tracking-wider text-neutral-800",
    caption,
  );
  const name = el(
    "span",
    `truncate font-sans text-sm font-semibold ${user ? "text-foreground" : "italic text-neutral-800"}`,
    user ? user.name : fallbackName,
  );
  if (user) name.title = user.name;

  text.append(label, name);
  if (captionNode) {
    const meta = el("span", "truncate font-sans text-xs text-neutral-800");
    meta.append(captionNode);
    text.append(meta);
  }

  person.append(createAvatarElement(user), text);
  return person;
}

/* ============================== CLIPBOARD ============================= */

export async function copyToClipboard(value) {
  if (navigator.clipboard && window.isSecureContext) {
    await navigator.clipboard.writeText(value);
    return;
  }

  // Fallback for non-secure contexts (e.g. LAN dev server over http)
  const textarea = el("textarea", "fixed -left-[9999px] opacity-0");
  textarea.value = value;
  document.body.append(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) throw new Error("Copy command was rejected");
}
