(function () {
  if (window.__passwordToggleInitialized) return;
  window.__passwordToggleInitialized = true;

  document.addEventListener("click", (e) => {
    const button = e.target.closest(".toggle-password");
    if (!button) return;

    const input = document.getElementById(button.getAttribute("data-target"));
    const eyeIcon = button.querySelector(".eye-icon");
    const eyeOffIcon = button.querySelector(".eye-off-icon");
    if (!input || !eyeIcon || !eyeOffIcon) return;

    const isPassword = input.getAttribute("type") === "password";
    input.setAttribute("type", isPassword ? "text" : "password");

    eyeIcon.classList.toggle("opacity-100", !isPassword);
    eyeIcon.classList.toggle("opacity-0", isPassword);
    eyeIcon.classList.toggle("scale-100", !isPassword);
    eyeIcon.classList.toggle("scale-75", isPassword);
    eyeIcon.classList.toggle("pointer-events-none", isPassword);

    eyeOffIcon.classList.toggle("opacity-100", isPassword);
    eyeOffIcon.classList.toggle("opacity-0", !isPassword);
    eyeOffIcon.classList.toggle("scale-100", isPassword);
    eyeOffIcon.classList.toggle("scale-75", !isPassword);
    eyeOffIcon.classList.toggle("pointer-events-none", !isPassword);

    button.setAttribute(
      "aria-label",
      isPassword ? "Hide password" : "Show password",
    );
  });
})();
