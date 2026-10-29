// Error page interactions (templates/errors/): the pointer light, falling leaves, the
// growth ring in the middle of the code, the 404 garden and the 403 lock. Without JS
// the pages still show plain rings, the message and every link.

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = window.matchMedia("(pointer: fine)").matches;
const SVG_NS = "http://www.w3.org/2000/svg";

const random = (min, max) => Math.random() * (max - min) + min;
const pick = (items) => items[Math.floor(Math.random() * items.length)];

/* ============================== GROWTH RING ============================== */

// A closed, slightly irregular ring (a few low-frequency waves on the radius),
// joined with smooth curves so it looks like a real tree ring
function ringPath(radius, wobble, center = 260) {
  const waves = [2, 3, 5].map((frequency) => ({
    frequency,
    phase: Math.random() * Math.PI * 2,
    amount: (Math.random() * wobble) / frequency,
  }));

  const steps = 60;
  const points = [];
  for (let i = 0; i < steps; i++) {
    const angle = (i / steps) * Math.PI * 2;
    const offset = waves.reduce((sum, w) => sum + Math.sin(angle * w.frequency + w.phase) * w.amount, 0);
    points.push([center + Math.cos(angle) * (radius + offset), center + Math.sin(angle) * (radius + offset)]);
  }

  // Catmull-Rom through the points, written as cubic Béziers
  let d = `M${points[0][0].toFixed(1)} ${points[0][1].toFixed(1)}`;
  for (let i = 0; i < steps; i++) {
    const p0 = points[(i - 1 + steps) % steps];
    const p1 = points[i];
    const p2 = points[(i + 1) % steps];
    const p3 = points[(i + 2) % steps];
    const c1 = [p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6];
    const c2 = [p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6];
    d += ` C${c1[0].toFixed(1)} ${c1[1].toFixed(1)} ${c2[0].toFixed(1)} ${c2[1].toFixed(1)} ${p2[0].toFixed(1)} ${p2[1].toFixed(1)}`;
  }
  return `${d} Z`;
}

function drawIn(path, delay = 0) {
  if (prefersReducedMotion) return;
  const length = path.getTotalLength();
  path.style.strokeDasharray = `${length}`;
  path.style.strokeDashoffset = `${length}`;
  path.style.transition = `stroke-dashoffset 1.4s cubic-bezier(0.22, 1, 0.36, 1) ${delay}ms`;
  requestAnimationFrame(() => requestAnimationFrame(() => (path.style.strokeDashoffset = "0")));
  setTimeout(() => {
    path.style.strokeDasharray = "";
    path.style.transition = "";
  }, 1500 + delay);
}

const RING_PALETTES = {
  default: ["stroke-secondary-300", "stroke-primary-300", "stroke-secondary-200", "stroke-primary-400", "stroke-tertiary-400", "stroke-primary-300", "stroke-secondary-300"],
  locked: ["stroke-tertiary-400", "stroke-secondary-300", "stroke-tertiary-300", "stroke-secondary-200", "stroke-tertiary-500", "stroke-secondary-300"],
};

// Replace the plain fallback circles with hand-made rings, drawn in from the outside
function initRings() {
  document.querySelectorAll("[data-rings]").forEach((svg) => {
    const count = Number(svg.dataset.ringCount) || 6;
    const palette = RING_PALETTES[svg.dataset.ringPalette] || RING_PALETTES.default;
    svg.replaceChildren();

    for (let i = 0; i < count; i++) {
      const radius = 245 - i * (175 / count);
      const path = document.createElementNS(SVG_NS, "path");
      path.setAttribute("d", ringPath(radius, 16));
      path.setAttribute("fill", "none");
      path.setAttribute("stroke-width", i === 0 ? "7" : "5");
      path.setAttribute("stroke-linecap", "round");
      path.setAttribute("class", `error-ring-line ${palette[i % palette.length]}`);
      path.style.setProperty("--ring-i", i);
      svg.append(path);
      drawIn(path, 200 + i * 110);
    }
  });
}

// A ripple spreads out of the ring when it's pressed
function ripple(ring) {
  if (prefersReducedMotion) return;
  const wave = document.createElement("span");
  wave.className = "error-ripple";
  wave.setAttribute("aria-hidden", "true");
  ring.append(wave);
  wave.addEventListener("animationend", () => wave.remove());
}

/* ============================== AMBIENCE ============================== */

// Soft light following the pointer, and the code drifting toward it a little.
// At most one update per frame.
function initPointer() {
  if (!finePointer || prefersReducedMotion) return;
  const page = document.querySelector("[data-error-page]");
  const layers = [...document.querySelectorAll("[data-parallax]")];
  let frame = 0;
  let x = 0;
  let y = 0;

  window.addEventListener("pointermove", (event) => {
    x = event.clientX;
    y = event.clientY;
    if (frame) return;
    frame = requestAnimationFrame(() => {
      frame = 0;
      page.style.setProperty("--glow-x", `${x}px`);
      page.style.setProperty("--glow-y", `${y}px`);
      const dx = x / window.innerWidth - 0.5;
      const dy = y / window.innerHeight - 0.5;
      layers.forEach((layer) => {
        const depth = Number(layer.dataset.depth) || 10;
        layer.style.translate = `${(dx * depth).toFixed(1)}px ${(dy * depth).toFixed(1)}px`;
      });
    });
  });
}

// The light inside each card follows the pointer (same cards as the landing page)
function initSpotlight() {
  document.querySelectorAll("[data-spotlight]").forEach((card) => {
    card.addEventListener("pointermove", (event) => {
      const rect = card.getBoundingClientRect();
      card.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
      card.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
    });
  });
}

const LEAF_SVG = `
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
    <path d="M11 20A7 7 0 0 1 9.8 6.2C15.5 3.7 20 4 20 4s.3 4.5-2.2 10.2A7 7 0 0 1 11 20Z" />
    <path d="M8 16c2.5-2.5 5-4.5 8-6" />
  </svg>`;

// A few leaves drifting down behind everything (styles: .falling-leaf in input.css)
function initLeaves() {
  const container = document.getElementById("falling-leaves");
  if (!container || prefersReducedMotion) return;
  const colors = ["#809352", "#99b062", "#aac46d", "#5f7a4f", "#c29ea6", "#dbb1ba"];
  const count = window.innerWidth < 768 ? 10 : 18;

  for (let i = 0; i < count; i++) {
    const leaf = document.createElement("span");
    const size = random(28, 52);
    leaf.className = "falling-leaf";
    leaf.style.position = "absolute";
    leaf.style.left = `${random(-5, 105)}%`;
    leaf.style.top = "-40px";
    leaf.style.width = `${size}px`;
    leaf.style.height = `${size}px`;
    leaf.style.color = pick(colors);
    leaf.style.opacity = random(0.12, 0.3);
    leaf.style.animationDuration = `${random(14, 26)}s`;
    leaf.style.animationDelay = `${random(-26, 0)}s`;
    leaf.style.setProperty("--drift-x", `${random(-100, 100)}px`);
    leaf.style.setProperty("--rotation", `${random(240, 600)}deg`);
    leaf.innerHTML = LEAF_SVG;
    container.append(leaf);
  }
}

// The underline under the headline draws itself in
function initDraw() {
  document.querySelectorAll("[data-draw]").forEach((path) => drawIn(path, 700));
}

// "Halaman sebelumnya" only shows when there is a page of ours to go back to
function initBack() {
  let cameFromHere = false;
  try {
    cameFromHere = document.referrer && new URL(document.referrer).origin === location.origin;
  } catch {
    cameFromHere = false;
  }
  if (!cameFromHere || history.length < 2) return;

  document.querySelectorAll("[data-back]").forEach((button) => {
    button.hidden = false;
    button.addEventListener("click", () => history.back());
  });
}

/* ============================== 404: THE GARDEN ============================== */

const SPROUT_COLORS = ["#809352", "#889d57", "#99b062", "#aac46d", "#5f7a4f", "#667641"];
const BLOOM_COLORS = ["#f3c5cf", "#dbb1ba", "#fff49b", "#fffffe"];
const MAX_SPROUTS = 24;

// A small plant: a curved stem, two leaves and sometimes a flower on top
function sproutSvg(height) {
  const lean = random(-10, 10);
  const stem = pick(SPROUT_COLORS);
  const leaf = pick(SPROUT_COLORS);
  const top = 100 - height;
  const bloom = Math.random() < 0.35
    ? `<circle class="sprout-bloom" cx="${30 + lean}" cy="${top}" r="5.5" fill="${pick(BLOOM_COLORS)}" stroke="#92767c" stroke-opacity="0.35" />`
    : "";
  const leafY = top + height * 0.45;
  return `
    <svg viewBox="0 0 60 100" class="h-full w-full overflow-visible" aria-hidden="true">
      <path class="sprout-stem" d="M30 100 Q ${30 + lean * 1.4} ${100 - height / 2} ${30 + lean} ${top}" fill="none" stroke="${stem}" stroke-width="3" stroke-linecap="round" />
      <path class="sprout-leaf sprout-leaf--left" d="M${30 + lean * 0.5} ${leafY} q -14 -4 -18 -16 q 14 0 18 16 Z" fill="${leaf}" />
      <path class="sprout-leaf sprout-leaf--right" d="M${30 + lean * 0.7} ${leafY - 8} q 14 -6 18 -18 q -14 2 -18 18 Z" fill="${leaf}" />
      ${bloom}
    </svg>`;
}

function initGarden() {
  const garden = document.querySelector("[data-garden]");
  const soil = garden?.querySelector("[data-soil]");
  if (!garden || !soil) return;
  const counter = garden.querySelector("[data-plant-count]");
  const ring = garden.querySelector("[data-ring]");
  let planted = 0;

  function plant(xRatio, { count = true } = {}) {
    const sprout = document.createElement("span");
    const height = random(42, 82);
    sprout.className = "sprout";
    sprout.style.left = `${Math.min(Math.max(xRatio, 0.03), 0.97) * 100}%`;
    sprout.style.setProperty("--sprout-scale", random(0.75, 1.15).toFixed(2));
    sprout.innerHTML = sproutSvg(height);
    soil.append(sprout);

    // Keep the garden light: the oldest sprout wilts away
    const sprouts = soil.querySelectorAll(".sprout:not(.is-wilting)");
    if (sprouts.length > MAX_SPROUTS) {
      const oldest = sprouts[0];
      oldest.classList.add("is-wilting");
      setTimeout(() => oldest.remove(), 600);
    }

    if (!count) return;
    planted += 1;
    if (counter) counter.textContent = planted;
  }

  // A few sprouts are already growing, so the soil never starts bare
  [0.12, 0.27, 0.71, 0.86].forEach((x, i) => {
    setTimeout(() => plant(x + random(-0.04, 0.04), { count: false }), 900 + i * 160);
  });

  garden.addEventListener("click", (event) => {
    // Buttons and links inside the garden do their own thing
    if (event.target.closest("button, a")) return;
    const rect = garden.getBoundingClientRect();
    plant((event.clientX - rect.left) / rect.width);
  });

  garden.querySelector("[data-plant-button]")?.addEventListener("click", () => plant(random(0.05, 0.95)));

  // The ring scatters a little handful of seeds
  ring?.addEventListener("click", () => {
    ripple(ring);
    for (let i = 0; i < 3; i++) setTimeout(() => plant(random(0.08, 0.92)), i * 140);
  });
}

/* ============================== 403: THE LOCK ============================== */

const LOCK_MESSAGES = [
  "Kawasan ini sedang dipulihkan. Mohon tidak masuk dulu.",
  "Hanya penjaga hutan yang memegang kuncinya.",
  "Sudah dicoba lagi? Gemboknya tetap rapat.",
  "Pohon-pohon di dalam sedang beristirahat.",
  "Masuk dengan akun yang tepat untuk membukanya.",
  "Kalau ini keliru, Help Desk siap membantu.",
];

function initLock() {
  const lock = document.querySelector("[data-lock]");
  if (!lock) return;
  const message = document.querySelector("[data-lock-message]");
  const icon = lock.querySelector("[data-lock-icon]");
  let index = 0;

  lock.addEventListener("click", () => {
    ripple(lock);
    index = (index + 1) % LOCK_MESSAGES.length;
    if (message) message.textContent = LOCK_MESSAGES[index];

    if (!icon || prefersReducedMotion) return;
    // Restart the shake even on quick repeated taps
    icon.classList.remove("is-shaking");
    void icon.offsetWidth;
    icon.classList.add("is-shaking");
  });
}

initRings();
initPointer();
initSpotlight();
initLeaves();
initDraw();
initBack();
initGarden();
initLock();
