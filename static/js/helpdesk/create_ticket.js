import "./../components/toast/toast.js";
import { createAttachmentPicker } from "./attachments.js";
import { setButtonLoading, setButtonText } from "./shared.js";

const MODAL_ID = "createTicketModal";

const form = document.getElementById("createTicketForm");
const submitButton = document.getElementById("createTicketSubmit");
const attachments = form ? createAttachmentPicker(form.querySelector("[data-attachments]")) : null;

// Each validated field, with where its error and character count go
const FIELDS = {
  subject: {
    input: document.getElementById("ticketSubject"),
    error: document.getElementById("ticketSubjectError"),
    count: document.getElementById("ticketSubjectCount"),
    requiredMessage: "Beri judul singkat untuk tiketmu.",
  },
  description: {
    input: document.getElementById("ticketDescription"),
    error: document.getElementById("ticketDescriptionError"),
    count: document.getElementById("ticketDescriptionCount"),
    requiredMessage: "Ceritakan masalahnya supaya kami bisa bantu.",
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

  if (errors.attachments?.length) attachments.setError(errors.attachments.join(" "));

  // Errors on fields without an inline slot (e.g. priority) go to a toast
  const otherErrors = Object.entries(errors)
    .filter(([field]) => !FIELDS[field] && field !== "attachments")
    .map(([, messages]) => messages[0]);
  if (otherErrors.length) {
    window.showToast?.({
      type: "error",
      title: "Tiket gagal dibuat",
      message: otherErrors.join(" "),
    });
  }

  firstInvalid?.focus();
}

function resetForm() {
  form.reset();
  attachments.reset();
  clearFieldErrors();
  Object.keys(FIELDS).forEach(updateCount);
  FIELDS.description.input.style.height = "";
}

// fetch() can't report upload progress, so screenshots go through XHR. Resolves with
// what the caller needs from the response; rejects only on network failure.
function postWithProgress(url, body, onProgress) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    request.open("POST", url);
    request.setRequestHeader("Accept", "application/json");
    request.upload.addEventListener("progress", (event) => {
      if (event.lengthComputable) onProgress(event.loaded / event.total);
    });
    request.addEventListener("load", () =>
      resolve({
        ok: request.status >= 200 && request.status < 300,
        status: request.status,
        contentType: request.getResponseHeader("content-type") || "",
        json: () => JSON.parse(request.responseText),
      }),
    );
    request.addEventListener("error", () => reject(new Error("Koneksi bermasalah. Cek internetmu lalu coba lagi.")));
    request.send(body);
  });
}

async function submitTicket(event) {
  // Without JS the form posts normally; with JS we stay on the page
  event.preventDefault();
  if (submitButton.getAttribute("aria-busy") === "true") return;
  if (!validateForm()) return;

  // aria-busy (checked above) blocks double submits; not `disabled`, which
  // would dim the button and make it look broken while it's working
  setButtonLoading(submitButton, true, attachments.count ? "Mengunggah…" : "Membuat…");

  try {
    // FormData includes the csrfmiddlewaretoken from {% csrf_token %}
    const body = new FormData(form);
    attachments.appendTo(body);
    const response = await postWithProgress(form.dataset.apiUrl, body, (fraction) => {
      if (!attachments.hasFiles) return;
      attachments.setUploadProgress(fraction);
      setButtonText(submitButton, `Uploading ${Math.round(fraction * 100)}%`);
    });

    if (!response.contentType.includes("application/json"))
      throw new Error("Server tidak merespons dengan benar. Sesimu mungkin sudah habis.");
    const data = response.json();

    if (response.status === 400 && data.errors) {
      showServerErrors(data.errors);
      return;
    }
    if (!response.ok) throw new Error(`Tiket gagal dibuat (${response.status})`);

    window.closeModal(MODAL_ID);
    resetForm();

    window.showToast?.({
      type: "success",
      title: "Tiket berhasil dibuat",
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
      title: "Tiket gagal dibuat",
      message: error.message,
    });
  } finally {
    attachments.setUploadProgress(null);
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
