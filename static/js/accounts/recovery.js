// Every page of the password reset flow (templates/accounts/_recovery_base.html):
// falling leaves like the login page, and Django messages as toasts.
import { prefersReducedMotion, showMessagesAsToasts } from "./shared.js";

const LEAF_COLORS = ["#809352", "#889d57", "#99b062", "#aac46d", "#5f7a4f", "#c29ea6", "#dbb1ba"];

const random = (min, max) => Math.random() * (max - min) + min;

// Same leaves as templates/accounts/login.html (styles: .falling-leaf in static/src/input.css)
function growLeaves(container) {
  if (!container || prefersReducedMotion()) return;
  const count = window.innerWidth < 768 ? 30 : 50;

  for (let i = 0; i < count; i++) {
    const leaf = document.createElement("span");
    const size = random(40, 60);
    leaf.className = "falling-leaf";
    Object.assign(leaf.style, {
      position: "absolute",
      left: `${random(-5, 105)}%`,
      top: "-40px",
      width: `${size}px`,
      height: `${size}px`,
      color: LEAF_COLORS[Math.floor(Math.random() * LEAF_COLORS.length)],
      opacity: random(0.12, 0.28),
      animationDuration: `${random(12, 24)}s`,
      animationDelay: `${random(-24, 0)}s`,
    });
    leaf.style.setProperty("--drift-x", `${random(-100, 100)}px`);
    leaf.style.setProperty("--rotation", `${random(240, 600)}deg`);
    leaf.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
        <path d="M11 20A7 7 0 0 1 9.8 6.2C15.5 3.7 20 4 20 4s.3 4.5-2.2 10.2A7 7 0 0 1 11 20Z" />
        <path d="M8 16c2.5-2.5 5-4.5 8-6" />
      </svg>`;
    container.appendChild(leaf);
  }
}

growLeaves(document.getElementById("falling-leaves"));

// "Send another link" (password_reset_done.html) unlocks after data-cooldown seconds,
// so an impatient second click doesn't flood the inbox
function startCooldown(link) {
  const note = document.querySelector("[data-cooldown-note]");
  const lockedClasses = ["pointer-events-none", "opacity-45"];
  let remaining = Number(link.dataset.cooldown) || 0;
  if (!remaining) return;

  const block = (event) => event.preventDefault();
  link.setAttribute("aria-disabled", "true");
  link.classList.add(...lockedClasses);
  link.addEventListener("click", block);

  const tick = () => {
    if (remaining <= 0) {
      clearInterval(timer);
      link.removeAttribute("aria-disabled");
      link.classList.remove(...lockedClasses);
      link.removeEventListener("click", block);
      if (note) note.textContent = "Masih belum masuk? Sekarang kamu bisa minta tautan baru.";
      return;
    }
    if (note) note.textContent = `Kamu bisa minta tautan baru dalam ${remaining} detik.`;
    remaining -= 1;
  };
  const timer = setInterval(tick, 1000);
  tick();
}

document.querySelectorAll("[data-cooldown]").forEach(startCooldown);

showMessagesAsToasts();
