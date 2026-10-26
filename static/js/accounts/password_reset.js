// Password reset page (templates/accounts/password_reset.html): falling leaves
// like the login page, an email check before sending and a loading button.
import {
  looksLikeEmail,
  prefersReducedMotion,
  setButtonLoading,
  showMessagesAsToasts,
} from "./shared.js";

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

const form = document.querySelector("[data-reset-form]");

if (form) {
  const email = form.querySelector("#id_email");
  const submit = form.querySelector('button[type="submit"]');

  form.addEventListener("submit", (event) => {
    if (!looksLikeEmail(email.value.trim())) {
      event.preventDefault();
      email.focus();
      email.classList.add("border-tertiary-600");
      email.setAttribute("aria-invalid", "true");
      window.showToast?.({
        type: "error",
        title: "Check your email",
        message: "Enter the email address you signed up with.",
      });
      return;
    }
    setButtonLoading(submit);
  });

  email.addEventListener("input", () => {
    email.classList.remove("border-tertiary-600");
    email.removeAttribute("aria-invalid");
  });
}

showMessagesAsToasts();
