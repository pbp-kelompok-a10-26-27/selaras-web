// Code shared by the account pages (profile.js, password.js, password_reset.js).

const TOAST_TITLES = {
  success: "Done",
  error: "Something went wrong",
  warning: "Heads up",
  info: "Note",
};

export const prefersReducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

// Shows the Django messages rendered by templates/accounts/_messages.html as toasts
export function showMessagesAsToasts() {
  const source = document.getElementById("account-messages");
  if (!source || typeof window.showToast !== "function") return;

  let messages = [];
  try {
    messages = JSON.parse(source.textContent);
  } catch {
    return;
  }

  messages.forEach(({ level, text }, index) => {
    // A message can carry extra tags ("extra success"); the level is the last one
    const tag = level.split(" ").pop();
    const type = tag in TOAST_TITLES ? tag : "info";
    setTimeout(
      () => window.showToast({ type, title: TOAST_TITLES[type], message: text }),
      300 + index * 150,
    );
  });
}

// Puts the button component into its loading state while a form submits
export function setButtonLoading(button, loading = true) {
  if (!button) return;
  button.disabled = loading;
  button.setAttribute("aria-busy", String(loading));
  const spinner = button.querySelector("[data-button-spinner]");
  spinner?.classList.toggle("hidden", !loading);
  spinner?.classList.toggle("inline-flex", loading);
}

// Fades in .scroll-reveal blocks as they enter the screen (styles in static/src/input.css)
export function revealOnScroll() {
  const nodes = document.querySelectorAll(".scroll-reveal");
  if (!("IntersectionObserver" in window) || prefersReducedMotion()) {
    nodes.forEach((node) => node.classList.add("is-visible"));
    return;
  }

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        entry.target.classList.add("is-visible");
        observer.unobserve(entry.target);
      });
    },
    { threshold: 0.1, rootMargin: "0px 0px -40px 0px" },
  );
  nodes.forEach((node) => observer.observe(node));
}

// Good enough to catch typos; the server has the final say
export const looksLikeEmail = (value) => /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(value);
