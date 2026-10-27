// Admin challenge form: shows the status the challenge will have once saved.
import { showMessagesAsToasts } from "../accounts/shared.js";

showMessagesAsToasts();

const form = document.getElementById("challengeForm");
const preview = document.getElementById("challengeStatusPreview");

if (form && preview) {
  const field = (name) => form.elements[name];

  const today = () => {
    const now = new Date();
    const pad = (value) => String(value).padStart(2, "0");
    return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
  };

  // Mirrors Challenge.status on the server (ISO dates compare as strings)
  function currentStatus() {
    if (!field("is_published")?.checked) return "Draft";
    const start = field("start_date")?.value;
    const end = field("end_date")?.value;
    if (!start || !end) return "Published";
    if (end < today()) return "Ended";
    if (start > today()) return "Upcoming";
    return "Active";
  }

  const update = () => {
    preview.textContent = currentStatus();
  };

  ["is_published", "start_date", "end_date"].forEach((name) => {
    field(name)?.addEventListener("input", update);
    field(name)?.addEventListener("change", update);
  });
  update();
}
