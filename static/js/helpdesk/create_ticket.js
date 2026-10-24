import "./../components/toast/toast.js";
import { setButtonLoading } from "./shared.js";

const MODAL_ID = "createTicketModal";

const form = document.getElementById("createTicketForm");
const submitButton = document.getElementById("createTicketSubmit");

// Each validated field, with where its error and character count go
const FIELDS = {
  subject: {
    input: document.getElementById("ticketSubject"),
    error: document.getElementById("ticketSubjectError"),
    count: document.getElementById("ticketSubjectCount"),
    requiredMessage: "Give your ticket a short subject.",
  },
  description: {
    input: document.getElementById("ticketDescription"),
    error: document.getElementById("ticketDescriptionError"),
    count: document.getElementById("ticketDescriptionCount"),
    requiredMessage: "Describe the problem so we can help.",
  },
};

function setFieldError(field, message) {
  const { input, error } = FIELDS[field];
  if (message) {
    input.setAttribute("aria-invalid", "true");
    error.textContent = message;
    error.hidden = false;
  } else {
    input.removeAttribute("aria-invalid");
    error.textContent = "";
    error.hidden = true;
  }
}

function clearFieldErrors() {
  Object.keys(FIELDS).forEach((field) => setFieldError(field, ""));
}

function updateCount(field) {
  const { input, count } = FIELDS[field];
  const length = input.value.length;
  count.textContent = `${length} / ${input.maxLength}`;
  // Warn as the limit gets close, instead of only after hitting it
  const nearLimit = length > input.maxLength * 0.9;
  count.classList.toggle("text-red-100", nearLimit);
  count.classList.toggle("font-semibold", nearLimit);
}

function autoResizeTextarea(textarea) {
  textarea.style.height = "auto";
  textarea.style.height = `${textarea.scrollHeight}px`;
}

// Quick checks in the browser for instant feedback; the server checks again
function validateForm() {
  let firstInvalid = null;

  Object.entries(FIELDS).forEach(([field, { input, requiredMessage }]) => {
    const invalid = input.value.trim() === "";
    setFieldError(field, invalid ? requiredMessage : "");
    if (invalid && !firstInvalid) firstInvalid = input;
  });

  firstInvalid?.focus();
  return !firstInvalid;
}

function showServerErrors(errors) {
  let firstInvalid = null;

  Object.entries(errors).forEach(([field, messages]) => {
    if (FIELDS[field]) {
      setFieldError(field, messages[0]);
      firstInvalid ??= FIELDS[field].input;
    }
  });

  // Errors on fields without an inline slot (e.g. priority) go to a toast
  const otherErrors = Object.entries(errors)
    .filter(([field]) => !FIELDS[field])
    .map(([, messages]) => messages[0]);
  if (otherErrors.length) {
    window.showToast?.({
      type: "error",
      title: "Couldn't create ticket",
      message: otherErrors.join(" "),
    });
  }

  firstInvalid?.focus();
}

function resetForm() {
  form.reset();
  clearFieldErrors();
  Object.keys(FIELDS).forEach(updateCount);
  FIELDS.description.input.style.height = "";
}

async function submitTicket(event) {
  // Without JS the form posts normally; with JS we stay on the page
  event.preventDefault();
  if (submitButton.getAttribute("aria-busy") === "true") return;
  if (!validateForm()) return;

  // aria-busy (checked above) blocks double submits; not `disabled`, which
  // would dim the button and make it look broken while it's working
  setButtonLoading(submitButton, true, "Creating…");

  try {
    const response = await fetch(form.dataset.apiUrl, {
      method: "POST",
      headers: { Accept: "application/json" },
      // FormData includes the csrfmiddlewaretoken from {% csrf_token %}
      body: new FormData(form),
    });

    const contentType = response.headers.get("content-type") || "";
    if (!contentType.includes("application/json"))
      throw new Error("Server did not return JSON. Your session may be expired");
    const data = await response.json();

    if (response.status === 400 && data.errors) {
      showServerErrors(data.errors);
      return;
    }
    if (!response.ok) throw new Error(`Failed to create ticket (${response.status})`);

    window.closeModal(MODAL_ID);
    resetForm();

    window.showToast?.({
      type: "success",
      title: "Ticket created",
      message: `#${data.ticket.id.slice(0, 8).toUpperCase()} · ${data.ticket.title}`,
    });

    // stats.js listens for this to show the ticket in the list and refresh the stats
    document.dispatchEvent(
      new CustomEvent("helpdesk:ticket-created", { detail: { ticket: data.ticket } }),
    );
  } catch (error) {
    console.error(error);
    // The modal stays open with everything the user typed
    window.showToast?.({
      type: "error",
      title: "Couldn't create ticket",
      message: error.message,
    });
  } finally {
    setButtonLoading(submitButton, false);
  }
}

function initCreateTicket() {
  if (!form || !submitButton) return;

  Object.entries(FIELDS).forEach(([field, { input }]) => {
    updateCount(field);
    input.addEventListener("input", () => {
      updateCount(field);
      // Clear the error as soon as the user starts fixing it
      if (input.getAttribute("aria-invalid") && input.value.trim()) setFieldError(field, "");
      if (input.tagName === "TEXTAREA") autoResizeTextarea(input);
    });
  });

  // Ctrl+Enter (Cmd+Enter on Mac) submits from any field
  form.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", submitTicket);

  // Closing the modal keeps what was typed (so an accidental close loses
  // nothing), but old error messages shouldn't greet the user next time
  document.getElementById(MODAL_ID)?.addEventListener("modal:close", clearFieldErrors);
}

initCreateTicket();
