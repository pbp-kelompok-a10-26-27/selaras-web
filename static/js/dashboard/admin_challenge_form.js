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
    if (!field("is_published")?.checked) return "Draf";
    const start = field("start_date")?.value;
    const end = field("end_date")?.value;
    if (!start || !end) return "Terbit";
    if (end < today()) return "Selesai";
    if (start > today()) return "Segera";
    return "Berjalan";
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

// Goal: the target number only applies to tracked goals; check-in uses the length
const goalType = form?.elements.goal_type;
const targetField = document.querySelector("[data-goal-target-field]");
const checkinNote = document.querySelector("[data-checkin-note]");
const goalUnit = document.querySelector("[data-goal-unit]");
const UNITS = {
  articles_read: "(artikel)",
  donation_amount: "(rupiah)",
  posts_created: "(postingan)",
  likes_received: "(suka)",
  comments_written: "(komentar)",
};

function paintGoal() {
  const checkIn = goalType.value === "check_in";
  targetField.classList.toggle("hidden", checkIn);
  checkinNote.classList.toggle("hidden", !checkIn);
  checkinNote.classList.toggle("flex", checkIn);
  goalUnit.textContent = UNITS[goalType.value] ?? "";
}

if (goalType && targetField && checkinNote) {
  goalType.addEventListener("change", paintGoal);
  paintGoal();
}
