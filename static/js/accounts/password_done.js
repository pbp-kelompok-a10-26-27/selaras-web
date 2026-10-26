// Password changed page (templates/accounts/password_change_done.html): counts
// down and returns to the profile, unless the user chooses to stay.
import { showMessagesAsToasts } from "./shared.js";

const notice = document.querySelector("[data-redirect]");

if (notice) {
  const count = notice.querySelector("[data-redirect-count]");
  let remaining = Number(notice.dataset.redirectSeconds) || 10;

  const timer = setInterval(() => {
    remaining -= 1;
    count.textContent = remaining;
    if (remaining <= 0) {
      clearInterval(timer);
      window.location.assign(notice.dataset.redirect);
    }
  }, 1000);

  notice.classList.replace("hidden", "flex");

  // Any sign the user wants to read or act here stops the countdown
  const stop = () => {
    clearInterval(timer);
    notice.textContent = "Take your time. Use the buttons above when you're ready.";
  };
  notice.querySelector("[data-redirect-cancel]").addEventListener("click", () => {
    stop();
    document.getElementById("doneProfile")?.focus();
  });
  document.addEventListener("keydown", stop, { once: true });
}

showMessagesAsToasts();
