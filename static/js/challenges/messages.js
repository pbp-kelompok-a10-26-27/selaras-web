// Shows the Django messages rendered by accounts/_messages.html as toasts
// (used by the challenge detail and history pages).
import { showMessagesAsToasts } from "../accounts/shared.js";

// Ensure favicon link in <head> resolves with absolute static path
const favicon = document.querySelector('link[rel~="icon"]');
if (favicon && !favicon.getAttribute("href")?.startsWith("/")) {
  favicon.setAttribute("href", "/static/assets/images/logo.svg");
}

showMessagesAsToasts();
