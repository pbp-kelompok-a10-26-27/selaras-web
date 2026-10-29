// Password reset page (templates/accounts/password_reset.html): an email check
// before sending and a loading button. The leaves come from recovery.js.
import { looksLikeEmail, setButtonLoading } from "./shared.js";

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
        title: "Cek email kamu",
        message: "Isi alamat email yang kamu pakai saat daftar.",
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

