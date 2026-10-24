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

const relativeTimeFormatter = new Intl.RelativeTimeFormat(undefined, {
  numeric: "auto",
});
const absoluteTimeFormatter = new Intl.DateTimeFormat(undefined, {
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
  return "just now";
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

export function renderLucideIcons(root) {
  if (window.lucide) {
    window.lucide.createIcons({ root });
  } else {
    console.warn("Lucide is not loaded. Icons will not be rendered.");
  }
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
  button.setAttribute("aria-label", `Copy ticket ID ${shortId}`);

  button.addEventListener("click", async (event) => {
    // Ticket cards are clickable; copying shouldn't open the ticket
    event.stopPropagation();

    try {
      await copyToClipboard(ticketId);
      // flashTooltip (components/tooltip/tooltip.js) shows the feedback, then
      // restores "Copy ticket ID" once the tooltip has faded out
      window.flashTooltip?.(wrapper, "Copied!");
      window.showToast?.({
        type: "success",
        title: "Ticket ID copied",
        message: `${shortId} is now in your clipboard.`,
        duration: 2500,
      });
    } catch {
      window.flashTooltip?.(wrapper, "Copy failed");
      window.showToast?.({
        type: "error",
        title: "Couldn't copy ticket ID",
        message: "Your browser blocked clipboard access.",
      });
    }
  });

  return wrapper;
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
