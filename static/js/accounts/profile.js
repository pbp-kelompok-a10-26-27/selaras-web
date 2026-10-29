// Profile page (templates/accounts/profile.html): live preview of the edits,
// profile strength, tabs, unsaved-changes guard, copy buttons and stat counters.
import {
  looksLikeEmail,
  prefersReducedMotion,
  revealOnScroll,
  setButtonLoading,
  showMessagesAsToasts,
} from "./shared.js";

const BIO_LIMIT = 200;

const root = document.querySelector("[data-profile]");

if (root) {
  const form = root.querySelector("[data-profile-form]");
  const fields = {
    first_name: form.querySelector("#id_first_name"),
    last_name: form.querySelector("#id_last_name"),
    email: form.querySelector("#id_email"),
    bio: form.querySelector("#id_bio"),
  };
  const username = root.dataset.username;
  // A form that came back with errors already holds unsaved input
  const hasServerErrors = form.dataset.hasErrors === "true";

  // ---------------------------- Live preview ---------------------------- //
  const preview = {
    name: root.querySelector("[data-preview-name]"),
    initials: root.querySelector("[data-preview-initials]"),
    bio: root.querySelector("[data-preview-bio]"),
    email: root.querySelector("[data-preview-email]"),
  };

  function updatePreview() {
    const first = fields.first_name.value.trim();
    const last = fields.last_name.value.trim();

    preview.name.textContent = [first, last].filter(Boolean).join(" ") || username;
    preview.initials.textContent =
      first || last
        ? `${first.charAt(0)}${last.charAt(0)}`.toUpperCase()
        : username.slice(0, 2).toUpperCase();

    const bio = fields.bio.value.trim();
    preview.bio.textContent = bio || preview.bio.dataset.emptyText;
    preview.bio.classList.toggle("italic", !bio);
    preview.bio.classList.toggle("text-neutral-700", !bio);
    preview.bio.classList.toggle("text-secondary-700", Boolean(bio));

    preview.email.textContent = fields.email.value.trim() || "—";
  }

  // --------------------------- Profile strength -------------------------- //
  const ring = root.querySelector("[data-completion-ring]");
  const fill = root.querySelector("[data-completion-fill]");
  const bar = root.querySelector("[data-completion-bar]");
  const message = root.querySelector("[data-completion-message]");
  const steps = root.querySelectorAll("[data-step]");

  function updateCompletion() {
    let done = 0;
    steps.forEach((step) => {
      const value = fields[step.dataset.step]?.value.trim() ?? "";
      const isDone = step.dataset.step === "email" ? looksLikeEmail(value) : Boolean(value);
      step.dataset.done = String(isDone);
      if (isDone) done += 1;
    });

    const percent = Math.round((done / steps.length) * 100);
    ring?.style.setProperty("--progress", percent);
    if (fill) fill.style.setProperty("--fill", `${percent}%`);
    bar?.setAttribute("aria-valuenow", percent);
    root.querySelectorAll("[data-completion-percent]").forEach((node) => {
      node.textContent = percent;
    });
    if (message) {
      message.textContent =
        percent === 100
          ? "Profilmu sudah lengkap. Mantap!"
          : "Profil yang lengkap memudahkan orang lain mengenalmu.";
    }
  }

  // ------------------------------ Bio counter ---------------------------- //
  const bioCount = root.querySelector("[data-bio-count]");

  function updateBioCount() {
    const length = fields.bio.value.length;
    const nearLimit = length >= BIO_LIMIT * 0.9;
    bioCount.textContent = `${length}/${BIO_LIMIT}`;
    bioCount.classList.toggle("text-tertiary-700", nearLimit);
    bioCount.classList.toggle("font-semibold", nearLimit);
    bioCount.classList.toggle("text-neutral-800", !nearLimit);
  }

  // ------------------------- Email check on blur ------------------------- //
  const emailError = root.querySelector("[data-email-error]");

  function showEmailError(invalid) {
    emailError.classList.toggle("hidden", !invalid);
    fields.email.classList.toggle("border-tertiary-600", invalid);
    if (invalid) fields.email.setAttribute("aria-invalid", "true");
    else fields.email.removeAttribute("aria-invalid");
  }

  // Only complains once the user has left the field (or tries to save)
  function checkEmail({ force = false } = {}) {
    const valid = looksLikeEmail(fields.email.value.trim());
    if (force || fields.email.dataset.touched) showEmailError(!valid);
    return valid;
  }

  fields.email.addEventListener("blur", () => {
    fields.email.dataset.touched = "true";
    checkEmail();
  });

  // --------------------------- Unsaved changes --------------------------- //
  const saveStatus = root.querySelector("[data-save-status]");
  const discard = form.querySelector("[data-discard]");
  const save = form.querySelector('button[type="submit"]');
  const initial = Object.fromEntries(
    Object.entries(fields).map(([name, field]) => [name, field.defaultValue]),
  );
  let submitting = false;

  const isDirty = () =>
    Object.entries(fields).some(([name, field]) => field.value !== initial[name]);

  function updateDirty() {
    const dirty = hasServerErrors || isDirty();
    form.dataset.dirty = String(dirty);
    saveStatus.textContent = dirty ? "Ada perubahan yang belum disimpan" : "Semua perubahan tersimpan";
    discard.disabled = !isDirty();
  }

  function refresh() {
    updatePreview();
    updateCompletion();
    updateBioCount();
    updateDirty();
    if (fields.email.dataset.touched) checkEmail();
  }

  form.addEventListener("input", refresh);

  // type="reset" restores the values the page was rendered with; "reset" fires
  // before the browser does that, so read the fields on the next frame
  form.addEventListener("reset", () => {
    delete fields.email.dataset.touched;
    showEmailError(false);
    requestAnimationFrame(refresh);
  });

  form.addEventListener("submit", (event) => {
    if (!checkEmail({ force: true })) {
      event.preventDefault();
      fields.email.focus();
      window.showToast?.({
        type: "error",
        title: "Cek email kamu",
        message: "Alamat email itu sepertinya belum benar.",
      });
      return;
    }
    submitting = true;
    setButtonLoading(save);
  });

  window.addEventListener("beforeunload", (event) => {
    if (submitting || !isDirty()) return;
    event.preventDefault();
    event.returnValue = "";
  });

  // Ctrl/Cmd + S saves from anywhere on the page
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
      event.preventDefault();
      if (isDirty()) form.requestSubmit(save);
    }
  });

  // --------------------------------- Tabs -------------------------------- //
  const tabs = [...root.querySelectorAll('[role="tab"]')];
  const indicator = root.querySelector("[data-tab-indicator]");
  const selectedTab = () => tabs.find((tab) => tab.getAttribute("aria-selected") === "true");

  function moveIndicator(tab) {
    if (!indicator || !tab) return;
    indicator.style.width = `${tab.offsetWidth}px`;
    indicator.style.translate = `${tab.offsetLeft}px 0`;
  }

  function selectTab(name, { focus = false, updateHash = true } = {}) {
    const target = tabs.find((tab) => tab.dataset.tab === name) ?? tabs[0];
    tabs.forEach((tab) => {
      const selected = tab === target;
      tab.setAttribute("aria-selected", String(selected));
      tab.tabIndex = selected ? 0 : -1;
      document.getElementById(tab.getAttribute("aria-controls")).hidden = !selected;
    });
    moveIndicator(target);
    if (focus) target.focus();
    if (updateHash) history.replaceState(null, "", `#${target.dataset.tab}`);
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => selectTab(tab.dataset.tab));
    // Arrow keys, Home and End move between tabs (WAI-ARIA tabs pattern)
    tab.addEventListener("keydown", (event) => {
      const moves = { ArrowRight: 1, ArrowLeft: -1, Home: -index, End: tabs.length - 1 - index };
      if (!(event.key in moves)) return;
      event.preventDefault();
      const next = tabs[(index + moves[event.key] + tabs.length) % tabs.length];
      selectTab(next.dataset.tab, { focus: true });
    });
  });

  window.addEventListener("resize", () => moveIndicator(selectedTab()));
  // The display font can load after first paint and change the tab widths
  document.fonts?.ready.then(() => moveIndicator(selectedTab()));

  // A form with errors always opens on the form; otherwise #security etc. picks the tab
  selectTab(hasServerErrors ? "details" : location.hash.slice(1), { updateHash: false });

  // Jump to a field: "Edit profile" in the hero, and each profile strength step
  function editField(name) {
    selectTab("details");
    const field = fields[name] ?? fields.first_name;
    field.scrollIntoView({ behavior: prefersReducedMotion() ? "auto" : "smooth", block: "center" });
    field.focus({ preventScroll: true });
  }

  root.querySelector("[data-edit-profile]")?.addEventListener("click", () => editField("first_name"));
  steps.forEach((step) => step.addEventListener("click", () => editField(step.dataset.step)));

  // ----------------------------- Copy buttons ---------------------------- //
  root.querySelectorAll("[data-copy]").forEach((button) => {
    button.addEventListener("click", async () => {
      const wrapper = button.closest("[data-tooltip-wrapper]");
      try {
        await navigator.clipboard.writeText(button.dataset.copy);
        window.flashTooltip?.(wrapper, "Tersalin!");
      } catch {
        window.flashTooltip?.(wrapper, "Gagal menyalin");
      }
    });
  });

  // ------------------------------ Stat counters --------------------------- //
  function countUp(node) {
    const target = Number(node.dataset.countTo) || 0;
    if (!target || prefersReducedMotion()) return;
    const duration = 900;
    const start = performance.now();
    const tick = (now) => {
      const progress = Math.min((now - start) / duration, 1);
      // Ease-out cubic: fast start, gentle landing on the real number
      node.textContent = Math.round(target * (1 - (1 - progress) ** 3));
      if (progress < 1) requestAnimationFrame(tick);
    };
    node.textContent = "0";
    requestAnimationFrame(tick);
  }

  if ("IntersectionObserver" in window) {
    const counterObserver = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        countUp(entry.target);
        counterObserver.unobserve(entry.target);
      });
    });
    root.querySelectorAll("[data-count-to]").forEach((node) => counterObserver.observe(node));
  }

  // ------------------------- Pointer-following light ---------------------- //
  function followPointer(element, xVar, yVar) {
    element?.addEventListener("pointermove", (event) => {
      const rect = element.getBoundingClientRect();
      element.style.setProperty(xVar, `${event.clientX - rect.left}px`);
      element.style.setProperty(yVar, `${event.clientY - rect.top}px`);
    });
  }

  if (!prefersReducedMotion()) {
    followPointer(root.querySelector("[data-profile-hero]"), "--glow-x", "--glow-y");
    root.querySelectorAll("[data-spotlight]").forEach((tile) => followPointer(tile, "--spot-x", "--spot-y"));
  }

  refresh();
  revealOnScroll();
  showMessagesAsToasts();
}
