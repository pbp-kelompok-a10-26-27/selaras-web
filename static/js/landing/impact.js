// Impact estimator (templates/landing/_impact.html): a jar that fills with what one
// habit saves, over a stretch of time, for one person or a crowd. The figures are
// rough per-person, per-day estimates (apps/core/landing.py), for illustration only.

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const MAX_DAYS = 365;
const MAX_PEOPLE = 1000;
const CROWD_STEPS = [1, 2, 5, 10, 20]; // people per dot

function format(value, digits = 1) {
  return new Intl.NumberFormat("id-ID", { maximumFractionDigits: digits }).format(value);
}

// One decimal for small fractional amounts (0,2 kg), whole numbers otherwise
function formatAmount(value) {
  const digits = value < 100 && !Number.isInteger(value) ? 1 : 0;
  return new Intl.NumberFormat("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

// "kira-kira setinggi Monas" / "3× tinggi Monas", against the biggest landmark it passes
function against(amount, landmarks, near, times) {
  const passed = landmarks.filter(([size]) => amount >= size * 0.8).pop();
  if (!passed) return null;
  const [size, name] = passed;
  const ratio = amount / size;
  return ratio < 1.5 ? `${near} ${name}` : `${format(ratio, ratio < 10 ? 1 : 0)}× ${times} ${name}`;
}

// A familiar comparison for each habit's total
const COMPARE = {
  // A 600 ml bottle is about 20 cm tall
  tumbler(bottles) {
    const metres = bottles * 0.2;
    const size = metres < 1 ? `${format(metres * 100, 0)} cm` : `${format(metres)} m`;
    const like = against(
      metres,
      [
        [1.7, "orang dewasa"],
        [7, "rumah dua lantai"],
        [25, "pohon kelapa"],
        [132, "Monas"],
      ],
      "kira-kira setinggi",
      "tinggi",
    );
    return `Jika ditumpuk, botolnya setinggi ${size}${like ? `, ${like}` : ""}.`;
  },
  // A thin shopping bag weighs about 5 g
  bag(bags) {
    const kg = bags * 0.005;
    const weight = kg < 1 ? `${format(kg * 1000, 0)} gram` : `${format(kg)} kg`;
    const like = against(
      kg,
      [
        [1, "sekantong gula"],
        [4, "kucing dewasa"],
        [60, "orang dewasa"],
        [1000, "mobil kecil"],
      ],
      "kira-kira seberat",
      "berat",
    );
    return `Plastik sebanyak ${weight}${like ? `, ${like}` : ""}, tidak perlu dibuat.`;
  },
  // A grown tree takes up roughly 22 kg of CO2 a year
  bike(kg) {
    const treeYears = kg / 22;
    if (treeYears < 1) return `Setara kerja satu pohon menyerap CO₂ selama ${format(treeYears * 365, 0)} hari.`;
    return `Setara serapan CO₂ ${format(treeYears, treeYears < 10 ? 1 : 0)} pohon selama setahun penuh.`;
  },
  // A 10 W LED lamp runs 100 hours on 1 kWh; a home uses roughly 100 kWh a month
  ac(kwh) {
    const hours = kwh * 100;
    if (hours < 48) return `Cukup untuk menyalakan lampu LED 10 W selama ${format(hours, 0)} jam.`;
    if (hours < 24 * 365) return `Cukup untuk menyalakan lampu LED 10 W selama ${format(hours / 24, 0)} hari tanpa henti.`;
    return `Setara pemakaian listrik ${format(kwh / 100, 0)} rumah selama sebulan.`;
  },
};

const daysText = (days) => (days === MAX_DAYS ? "1 tahun" : `${days} hari`);
const peopleText = (people) => `${format(people, 0)} orang`;
// The people slider is logarithmic: 0 -> 1 person, 300 -> 1.000 people
const peopleFromSlider = (value) => {
  const raw = 10 ** (value / 100);
  return raw < 20 ? Math.round(raw) : raw < 200 ? Math.round(raw / 5) * 5 : Math.round(raw / 10) * 10;
};
const sliderFromPeople = (people) => Math.round(Math.log10(people) * 100);

/* Rolling digits: each digit is a column of 0-9 that slides to its value */
function rollTo(node, text) {
  if (prefersReducedMotion) {
    node.textContent = text;
    return;
  }
  const shape = text.replace(/\d/g, "0");
  if (node.dataset.shape !== shape) {
    node.dataset.shape = shape;
    node.replaceChildren(
      ...[...text].map((char) => {
        const cell = document.createElement("span");
        if (!/\d/.test(char)) {
          cell.textContent = char;
          return cell;
        }
        cell.className = "impact-digit";
        const column = document.createElement("span");
        column.append(...Array.from({ length: 10 }, (_, n) => Object.assign(document.createElement("span"), { textContent: n })));
        cell.append(column);
        return cell;
      }),
    );
  }
  const digits = [...text].filter((char) => /\d/.test(char));
  // Next frame, so freshly built columns roll up from 0 instead of jumping
  requestAnimationFrame(() => {
    node.querySelectorAll(".impact-digit > span").forEach((column, i) => column.style.setProperty("--n", digits[i]));
  });
}

export function initImpact() {
  const form = document.querySelector("[data-impact]");
  const habits = JSON.parse(document.getElementById("habitData")?.textContent ?? "[]");
  if (!form || !habits.length) return;

  const daysInput = form.querySelector("#impactDays");
  const peopleInput = form.querySelector("#impactPeople");
  const daysOut = form.querySelector("[data-impact-days-out]");
  const peopleOut = form.querySelector("[data-impact-people-out]");
  const dayButtons = [...form.querySelectorAll("[data-impact-days]")];
  const peopleButtons = [...form.querySelectorAll("[data-impact-people]")];
  const crowd = [...form.querySelectorAll("[data-impact-crowd] span")];
  const crowdKey = form.querySelector("[data-impact-crowd-key]");

  const jar = document.querySelector("[data-impact-jar]");
  const fill = document.querySelector("[data-impact-fill]");
  const drops = document.querySelector("[data-impact-drops]");
  const label = document.querySelector("[data-impact-label]");
  const valueNode = document.querySelector("[data-impact-value]");
  const unitNode = document.querySelector("[data-impact-unit]");
  const noteNode = document.querySelector("[data-impact-note]");
  const compareNode = document.querySelector("[data-impact-compare]");
  const compareCard = compareNode.closest(".impact-compare");

  // The rolling digits are read out once, from a hidden copy, not digit by digit
  const spoken = document.createElement("span");
  spoken.className = "sr-only";
  valueNode.after(spoken);
  valueNode.setAttribute("aria-hidden", "true");

  crowd.forEach((dot, i) => dot.style.setProperty("--d", String(i)));
  let people = 1;
  let lastHabit = null;
  let lastValue = 0;

  // A few items tumble into the jar when the total changes
  function drop(habit, level) {
    if (prefersReducedMotion) return;
    const icon = document.querySelector(`[data-impact-icon="${habit.key}"]`);
    if (!icon) return;
    const fall = jar.clientHeight * (1 - level / 100) + jar.clientHeight * 0.05;
    for (let i = 0; i < 5; i++) {
      const item = document.createElement("span");
      item.className = "impact-drop";
      item.append(icon.content.cloneNode(true));
      item.style.left = `${12 + Math.random() * 64}%`;
      item.style.animationDelay = `${i * 90}ms`;
      item.style.setProperty("--fall", `${fall}px`);
      item.style.setProperty("--spin", `${(Math.random() - 0.5) * 300}deg`);
      item.addEventListener("animationend", () => item.remove(), { once: true });
      drops.append(item);
    }
  }

  function update() {
    const habit = habits.find((h) => h.key === new FormData(form).get("habit")) ?? habits[0];
    const days = Number(daysInput.value);
    const value = Math.round(habit.per_day * days * people * 10) / 10;

    daysOut.textContent = daysText(days);
    daysInput.setAttribute("aria-valuetext", daysText(days));
    daysInput.style.setProperty("--fill", `${((days - 1) / (MAX_DAYS - 1)) * 100}%`);
    dayButtons.forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.impactDays) === days)));

    peopleOut.textContent = peopleText(people);
    peopleInput.setAttribute("aria-valuetext", peopleText(people));
    peopleInput.style.setProperty("--fill", `${(Number(peopleInput.value) / Number(peopleInput.max)) * 100}%`);
    peopleButtons.forEach((b) => b.setAttribute("aria-pressed", String(Number(b.dataset.impactPeople) === people)));
    const perDot = CROWD_STEPS.find((step) => people / step <= crowd.length) ?? CROWD_STEPS.at(-1);
    const lit = Math.ceil(people / perDot);
    crowd.forEach((dot, i) => dot.toggleAttribute("data-on", i < lit));
    crowdKey.textContent = `1 titik = ${perDot} orang`;

    // Log scale, so a week alone still shows and a campus for a year still fits
    const max = habit.per_day * MAX_DAYS * MAX_PEOPLE;
    const level = 6 + 86 * (Math.log1p(value) / Math.log1p(max));
    fill.style.setProperty("--level", level.toFixed(1));
    fill.dataset.habit = habit.key;
    label.textContent = habit.label;

    rollTo(valueNode, formatAmount(value));
    spoken.textContent = `${formatAmount(value)} ${habit.unit}`;
    unitNode.textContent = habit.unit;
    noteNode.textContent = habit.note;
    const comparison = COMPARE[habit.key]?.(value) ?? "";
    if (compareNode.textContent !== comparison) {
      compareNode.textContent = comparison;
      compareCard.removeAttribute("data-bump");
      void compareCard.offsetWidth;
      compareCard.setAttribute("data-bump", "");
    }

    if (habit !== lastHabit || value > lastValue) drop(habit, level);
    lastHabit = habit;
    lastValue = value;
  }

  form.addEventListener("change", update);
  daysInput.addEventListener("input", update);
  peopleInput.addEventListener("input", () => {
    people = peopleFromSlider(Number(peopleInput.value));
    update();
  });
  dayButtons.forEach((button) =>
    button.addEventListener("click", () => {
      daysInput.value = button.dataset.impactDays;
      update();
    }),
  );
  peopleButtons.forEach((button) =>
    button.addEventListener("click", () => {
      people = Number(button.dataset.impactPeople);
      peopleInput.value = String(sliderFromPeople(people));
      update();
    }),
  );
  form.addEventListener("submit", (event) => event.preventDefault());

  // First fill when the jar comes into view
  lastHabit = habits[0];
  const observer = new IntersectionObserver(
    (entries) => {
      if (!entries[0].isIntersecting) return;
      observer.disconnect();
      lastValue = 0;
      lastHabit = null;
      update();
    },
    { threshold: 0.4 },
  );
  fill.style.setProperty("--level", "4");
  observer.observe(jar);
}
