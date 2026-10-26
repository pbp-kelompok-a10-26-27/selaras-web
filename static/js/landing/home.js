// Landing page interactions: the meadow hero, the manifesto, the growth rings, live
// counters, the sticky layer index and the impact estimator. Without JS the page still
// shows plain rings, numbers and the default estimate.

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const finePointer = window.matchMedia("(pointer: fine)").matches;
const SVG_NS = "http://www.w3.org/2000/svg";
const CENTER = 260;
const numberFormat = new Intl.NumberFormat("id-ID");

/* ============================== RING GEOMETRY ============================== */

// Small seeded random, so the rings look hand-made but identical on every visit
function seededRandom(seed) {
  let t = seed >>> 0;
  return () => {
    t += 0x6d2b79f5;
    let r = Math.imul(t ^ (t >>> 15), 1 | t);
    r ^= r + Math.imul(r ^ (r >>> 7), 61 | r);
    return ((r ^ (r >>> 14)) >>> 0) / 4294967296;
  };
}

// A closed, slightly irregular ring like a real growth ring: the radius wobbles
// with a few low-frequency waves, then the points are joined with smooth curves.
function ringPath(radius, seed, wobble, center = CENTER) {
  const random = seededRandom(seed);
  const waves = [2, 3, 5, 7].map((frequency) => ({
    frequency,
    phase: random() * Math.PI * 2,
    amount: random() * wobble / frequency,
  }));

  const steps = 72;
  const points = [];
  for (let i = 0; i < steps; i++) {
    const angle = (i / steps) * Math.PI * 2;
    const offset = waves.reduce((sum, w) => sum + Math.sin(angle * w.frequency + w.phase) * w.amount, 0);
    const r = radius + offset;
    points.push([center + Math.cos(angle) * r, center + Math.sin(angle) * r]);
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
  // Clear the dash once drawn, so hover width changes don't show a seam
  setTimeout(() => {
    path.style.strokeDasharray = "";
    path.style.transition = "";
  }, 1500 + delay);
}

/* ============================== HERO ============================== */

// The meadow drifts slower than the page while scrolling and follows the mouse a
// little; a soft light follows the pointer. At most one update per frame.
function initHero() {
  const hero = document.querySelector("[data-hero]");
  const image = hero?.querySelector("[data-hero-image]");
  if (!hero || !image || prefersReducedMotion) return;
  const glow = hero.querySelector("[data-hero-glow]");

  let pointerX = 0;
  let pointerY = 0;
  let frame = 0;
  function render() {
    frame = 0;
    const scroll = Math.min(window.scrollY, hero.offsetHeight);
    image.style.setProperty("--hero-x", `${(pointerX * -14).toFixed(1)}px`);
    image.style.setProperty("--hero-y", `${(scroll * 0.25 + pointerY * -10).toFixed(1)}px`);
  }
  const schedule = () => {
    frame ||= requestAnimationFrame(render);
  };

  window.addEventListener("scroll", schedule, { passive: true });
  if (finePointer) {
    hero.addEventListener("pointermove", (event) => {
      const rect = hero.getBoundingClientRect();
      pointerX = (event.clientX - rect.left) / rect.width - 0.5;
      pointerY = (event.clientY - rect.top) / rect.height - 0.5;
      glow?.style.setProperty("--glow-x", `${event.clientX - rect.left}px`);
      glow?.style.setProperty("--glow-y", `${event.clientY - rect.top}px`);
      schedule();
    });
  }
  render();
}

/* ============================== MANIFESTO ============================== */

// Words brighten one by one as the paragraph moves up through the screen
function initManifesto() {
  const paragraph = document.querySelector("[data-manifesto]");
  if (!paragraph || prefersReducedMotion) return;

  const words = paragraph.textContent.trim().split(/\s+/);
  // Screen readers read the sentence once, not word by word
  paragraph.setAttribute("aria-label", words.join(" "));
  paragraph.replaceChildren(
    ...words.flatMap((word, i) => {
      const span = document.createElement("span");
      span.className = "word";
      span.setAttribute("aria-hidden", "true");
      span.textContent = word;
      return i ? [" ", span] : [span];
    }),
  );
  const spans = [...paragraph.querySelectorAll(".word")];

  let frame = 0;
  function update() {
    frame = 0;
    const rect = paragraph.getBoundingClientRect();
    // 0 when the paragraph's top reaches 85% of the screen, 1 when its bottom reaches 45%
    const start = window.innerHeight * 0.85;
    const end = window.innerHeight * 0.45;
    const progress = (start - rect.top) / (start - end + rect.height);
    const lit = Math.round(Math.min(Math.max(progress, 0), 1) * spans.length);
    spans.forEach((span, i) => span.classList.toggle("is-lit", i < lit));
  }
  window.addEventListener(
    "scroll",
    () => {
      frame ||= requestAnimationFrame(update);
    },
    { passive: true },
  );
  update();
}

/* ============================== GROWTH RINGS ============================== */

function initGrowthRings() {
  const svg = document.getElementById("growthRings");
  if (!svg) return;

  // 1. Swap the plain layer circles for hand-made rings (same classes and colours)
  const layers = {};
  [...svg.querySelectorAll("[data-ring]")].forEach((circle, index) => {
    const path = document.createElementNS(SVG_NS, "path");
    for (const attr of ["class", "stroke-width", "stroke-opacity", "data-ring"]) {
      path.setAttribute(attr, circle.getAttribute(attr));
    }
    path.setAttribute("d", ringPath(Number(circle.dataset.radius), 11 + index * 7, 9));
    path.setAttribute("stroke-linejoin", "round");
    circle.replaceWith(path);
    layers[path.dataset.ring] = path;
  });

  // 2. A few radial cracks (medullary rays), as on a real cross-section
  const rays = svg.querySelector("[data-rays]");
  const random = seededRandom(42);
  for (let i = 0; i < 9; i++) {
    const angle = random() * Math.PI * 2;
    const from = 30 + random() * 20;
    const to = 120 + random() * 110;
    const line = document.createElementNS(SVG_NS, "line");
    line.setAttribute("x1", CENTER + Math.cos(angle) * from);
    line.setAttribute("y1", CENTER + Math.sin(angle) * from);
    line.setAttribute("x2", CENTER + Math.cos(angle) * to);
    line.setAttribute("y2", CENTER + Math.sin(angle) * to);
    line.setAttribute("class", "stroke-secondary-900");
    line.setAttribute("stroke-opacity", "0.12");
    line.setAttribute("stroke-width", "1");
    line.setAttribute("stroke-linecap", "round");
    rays.append(line);
  }

  // 3. Daily rings: one thin ring per day, spread from the heartwood to the bark
  const dayGroup = svg.querySelector("[data-day-rings]");
  const slider = document.getElementById("growthDay");
  const output = document.getElementById("growthDayOutput");
  const dayLabel = svg.querySelector("[data-day-label]");
  const maxDays = Number(slider.max);
  const dayPaths = [];
  for (let day = 1; day <= maxDays; day++) {
    const radius = 32 + (day / maxDays) * 208;
    const path = document.createElementNS(SVG_NS, "path");
    // Same seed for every daily ring: they share one shape and nest without
    // crossing, like real growth rings (wobble grows a little with the radius)
    path.setAttribute("d", ringPath(radius, 77, 2 + radius / 40));
    path.setAttribute("class", "fill-none stroke-secondary-900 transition-opacity duration-300");
    path.setAttribute("stroke-width", day % 7 === 0 ? "1.6" : "0.8"); // every week a bit darker
    path.setAttribute("stroke-opacity", day % 7 === 0 ? "0.32" : "0.18");
    path.style.opacity = "0";
    dayGroup.append(path);
    dayPaths.push(path);
  }

  function showDays(days) {
    dayPaths.forEach((path, i) => (path.style.opacity = i < days ? "1" : "0"));
    slider.style.setProperty("--fill", `${((days - 1) / (maxDays - 1)) * 100}%`);
    dayLabel.textContent = days;
    const weeks = Math.floor(days / 7);
    output.textContent = `Hari ke-${days} · ${days} cincin harian${weeks ? ` · ${weeks} minggu` : ""}`;
  }
  slider.addEventListener("input", () => showDays(Number(slider.value)));

  // Once the diagram is on screen: the layers draw in from the heartwood out, then a
  // time-lapse grows the daily rings from day 1 to 30
  const target = Number(slider.value);
  if (prefersReducedMotion) {
    showDays(target);
  } else {
    const ringOrder = Object.values(layers).reverse(); // inside out
    ringOrder.forEach((path) => (path.style.opacity = "0"));
    slider.value = 1;
    showDays(1);

    let timer;
    let touched = false;
    // If the user grabs the slider first, stop (or skip) the time-lapse
    const stop = () => {
      touched = true;
      clearInterval(timer);
    };
    slider.addEventListener("pointerdown", stop, { once: true });
    slider.addEventListener("keydown", stop, { once: true });

    const start = new IntersectionObserver(
      (entries) => {
        if (!entries[0].isIntersecting) return;
        start.disconnect();
        ringOrder.forEach((path, i) => {
          path.style.opacity = "";
          drawIn(path, i * 160);
        });
        if (touched) return;
        let day = 1;
        setTimeout(() => {
          if (touched) return;
          timer = setInterval(() => {
            day += 1;
            slider.value = day;
            showDays(day);
            if (day >= target) clearInterval(timer);
          }, 45);
        }, 500);
      },
      { threshold: 0.35 },
    );
    start.observe(svg);
  }

  // 4. Hover / focus a layer (on the diagram or in the legend): highlight it and explain it
  const info = JSON.parse(document.getElementById("ringInfoData")?.textContent ?? "{}");
  const card = document.getElementById("ringInfo");
  const legend = [...document.querySelectorAll("[data-ring-legend]")];
  const defaults = {
    kicker: card.querySelector("[data-info-kicker]").textContent,
    title: card.querySelector("[data-info-title]").textContent,
    text: card.querySelector("[data-info-text]").textContent,
    swatch: "bg-secondary-700",
  };

  function setInfo({ kicker, title, text, swatch }) {
    card.querySelector("[data-info-kicker]").textContent = kicker;
    card.querySelector("[data-info-title]").textContent = title;
    card.querySelector("[data-info-text]").textContent = text;
    card.querySelector("[data-info-swatch]").className = `h-2.5 w-2.5 rounded-full ${swatch}`;
  }

  function highlight(key) {
    Object.entries(layers).forEach(([name, path]) => {
      const active = name === key;
      path.style.opacity = key && !active ? "0.25" : "";
      path.style.strokeWidth = active ? `${Number(path.getAttribute("stroke-width")) + 8}` : "";
    });
    setInfo(key && info[key] ? info[key] : defaults);
    legend.forEach((item) => item.setAttribute("aria-current", String(item.dataset.ringLegend === key)));
  }

  [...svg.querySelectorAll("[data-ring-link]"), ...legend].forEach((link) => {
    const key = link.dataset.ringLink ?? link.dataset.ringLegend;
    link.addEventListener("pointerenter", () => highlight(key));
    link.addEventListener("pointerleave", () => highlight(null));
    link.addEventListener("focus", () => highlight(key));
    link.addEventListener("blur", () => highlight(null));
  });
}

/* ============================ CARD SPOTLIGHT & TILT ============================ */

// Cards light up where the pointer is; the ring diagram tilts slightly towards it
function initPointerEffects() {
  if (!finePointer || prefersReducedMotion) return;
  document.querySelectorAll("[data-spotlight]").forEach((card) => {
    card.addEventListener("pointermove", (event) => {
      const rect = card.getBoundingClientRect();
      card.style.setProperty("--spot-x", `${event.clientX - rect.left}px`);
      card.style.setProperty("--spot-y", `${event.clientY - rect.top}px`);
    });
  });

  const tilt = document.querySelector("[data-tilt]");
  if (!tilt) return;
  tilt.style.transition = "transform 0.6s cubic-bezier(0.22, 1, 0.36, 1)";
  const area = tilt.closest("section");
  const clamp = (value) => Math.max(-0.6, Math.min(0.6, value));
  area.addEventListener("pointermove", (event) => {
    const rect = tilt.getBoundingClientRect();
    const x = clamp((event.clientX - rect.left) / rect.width - 0.5);
    const y = clamp((event.clientY - rect.top) / rect.height - 0.5);
    tilt.style.transform = `perspective(1200px) rotateX(${(y * -8).toFixed(2)}deg) rotateY(${(x * 8).toFixed(2)}deg)`;
  });
  area.addEventListener("pointerleave", () => (tilt.style.transform = ""));
}

/* ============================ IMPACT ESTIMATOR ============================ */

function formatAmount(value) {
  // One decimal for small fractional amounts (0,2 kg), whole numbers otherwise
  const digits = value < 100 && !Number.isInteger(value) ? 1 : 0;
  return new Intl.NumberFormat("id-ID", { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(value);
}

function initImpact() {
  const form = document.querySelector("[data-impact]");
  const habits = JSON.parse(document.getElementById("habitData")?.textContent ?? "[]");
  if (!form || !habits.length) return;

  const valueNode = document.querySelector("[data-impact-value]");
  const unitNode = document.querySelector("[data-impact-unit]");
  const noteNode = document.querySelector("[data-impact-note]");
  const rings = document.querySelector("[data-impact-rings]");
  let shown = 30;
  let frame = 0;

  // Faint rings behind the result: the longer the habit runs, the more rings
  function drawRings(days, animate = true) {
    const count = { 7: 3, 30: 7, 365: 14 }[days] ?? 7;
    rings.replaceChildren(
      ...Array.from({ length: count }, (_, i) => {
        const path = document.createElementNS(SVG_NS, "path");
        path.setAttribute("d", ringPath(18 + i * 13, 77, 2 + i * 0.6, 200));
        path.setAttribute("class", "fill-none stroke-primary-300");
        path.setAttribute("stroke-width", "1.5");
        return path;
      }),
    );
    // Measured once they're in the page (getTotalLength needs it)
    if (animate) [...rings.children].forEach((path, i) => drawIn(path, i * 50));
  }

  function animateTo(target) {
    cancelAnimationFrame(frame);
    if (prefersReducedMotion) {
      shown = target;
      valueNode.textContent = formatAmount(target);
      return;
    }
    const from = shown;
    const start = performance.now();
    const step = (now) => {
      const progress = Math.min((now - start) / 700, 1);
      shown = from + (target - from) * (1 - Math.pow(1 - progress, 3));
      valueNode.textContent = formatAmount(progress < 1 ? Math.round(shown) : target);
      if (progress < 1) frame = requestAnimationFrame(step);
      else shown = target;
    };
    frame = requestAnimationFrame(step);
  }

  let lastDays = 30;
  function update() {
    const data = new FormData(form);
    const habit = habits.find((h) => h.key === data.get("habit")) ?? habits[0];
    const days = Number(data.get("days"));
    const people = Number(data.get("people"));
    unitNode.textContent = habit.unit;
    noteNode.textContent = habit.note;
    if (days !== lastDays) drawRings(days);
    lastDays = days;
    animateTo(Math.round(habit.per_day * days * people * 10) / 10);
  }

  form.addEventListener("change", update);
  form.addEventListener("submit", (event) => event.preventDefault());
  drawRings(30, false);
}

/* ============================ COUNTERS & REVEALS ============================ */

function countUp(node) {
  const target = Number(node.dataset.count);
  if (!Number.isFinite(target)) return;
  if (prefersReducedMotion || target === 0) {
    node.textContent = numberFormat.format(target);
    return;
  }
  const start = performance.now();
  const duration = 1100;
  const step = (now) => {
    const progress = Math.min((now - start) / duration, 1);
    node.textContent = numberFormat.format(Math.round(target * (1 - Math.pow(1 - progress, 3))));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function initOnView() {
  // Counters and progress bars start at zero and fill when they come into view
  const counters = [...document.querySelectorAll("[data-count]")];
  counters.forEach((node) => (node.textContent = numberFormat.format(prefersReducedMotion ? Number(node.dataset.count) : 0)));

  // Widths come only from data-grow-width (an inline style="width: {{ }}%" trips the
  // editor's CSS checker); with reduced motion they're set straight away
  const bars = [...document.querySelectorAll("[data-grow-width]")];
  bars.forEach((bar) => (bar.style.width = prefersReducedMotion ? `${bar.dataset.growWidth}%` : "0%"));

  // Gentle fade-up for marked blocks (styles: .scroll-reveal in static/src/input.css)
  const reveals = prefersReducedMotion ? [] : [...document.querySelectorAll("[data-reveal]")];
  reveals.forEach((node) => node.classList.add("scroll-reveal"));

  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const node = entry.target;
        if (node.dataset.count !== undefined) countUp(node);
        if (node.dataset.growWidth !== undefined) node.style.width = `${node.dataset.growWidth}%`;
        if (node.hasAttribute("data-reveal")) node.classList.add("is-visible");
        observer.unobserve(node);
      });
    },
    // Fire as soon as a block starts entering the screen: tall blocks would
    // otherwise sit half-visible but still blank
    { threshold: 0, rootMargin: "0px 0px -8% 0px" },
  );
  [...counters, ...(prefersReducedMotion ? [] : bars), ...reveals].forEach((node) => observer.observe(node));
}

// Hero title underline, drawn in like a pen stroke after the words rise
function initDrawnStrokes() {
  document.querySelectorAll("[data-draw]").forEach((path) => drawIn(path, 900));
}

/* ========================= STICKY LAYER INDEX (scroll spy) ========================= */

function initLayerIndex() {
  const layers = [...document.querySelectorAll("[data-layer]")];
  const links = [...document.querySelectorAll("[data-index-link]")];
  const miniRings = [...document.querySelectorAll("[data-mini-ring]")];
  if (!layers.length || !links.length) return;

  function setCurrent(key) {
    links.forEach((link) => link.setAttribute("aria-current", String(link.dataset.indexLink === key)));
    // The mini ring lights up every layer up to the current one, like rings already grown
    const order = ["learn", "act", "share", "give"];
    const reached = order.indexOf(key);
    miniRings.forEach((ring) => ring.setAttribute("opacity", order.indexOf(ring.dataset.miniRing) <= reached ? "1" : "0.2"));
  }

  // The layer crossing the middle of the screen is the current one
  const observer = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) setCurrent(entry.target.dataset.layer);
      });
    },
    { rootMargin: "-45% 0px -45% 0px" },
  );
  layers.forEach((layer) => observer.observe(layer));
}

/* ============================ SCROLL PARALLAX ============================ */

// The few leaves drift slightly slower/faster than the page, for depth, and the
// closing section's log-end rings turn slowly. The offset is measured from the
// middle of the screen, so it stays small wherever an element sits. Uses the
// `translate` property, so it combines with the float animations (`transform`).
function initParallax() {
  if (prefersReducedMotion) return;
  const items = [...document.querySelectorAll("[data-parallax]")].map((node) => ({
    node,
    factor: Number(node.dataset.parallax) || 0,
    top: 0,
    height: 0,
  }));
  const ctaRings = document.querySelector("[data-cta-rings]");

  // Page positions without any parallax applied (re-measured on resize)
  function measure() {
    items.forEach((item) => {
      item.node.style.translate = "";
      const rect = item.node.getBoundingClientRect();
      item.top = rect.top + window.scrollY;
      item.height = rect.height;
    });
    update();
  }

  function update() {
    const viewportMiddle = window.scrollY + window.innerHeight / 2;
    items.forEach((item) => {
      const distance = item.top + item.height / 2 - viewportMiddle;
      // Off-screen items don't need work
      if (Math.abs(distance) > window.innerHeight * 1.5) return;
      item.node.style.translate = `0 ${(distance * item.factor).toFixed(1)}px`;
    });
    if (ctaRings) ctaRings.style.rotate = `${(window.scrollY * 0.02).toFixed(2)}deg`;
  }

  let ticking = false;
  window.addEventListener(
    "scroll",
    () => {
      if (ticking) return;
      ticking = true;
      requestAnimationFrame(() => {
        update();
        ticking = false;
      });
    },
    { passive: true },
  );

  let resizeTimer;
  window.addEventListener("resize", () => {
    clearTimeout(resizeTimer);
    resizeTimer = setTimeout(measure, 150);
  });

  // Fonts and images change the layout after load; measure once it settles
  measure();
  window.addEventListener("load", measure, { once: true });
}

initHero();
initManifesto();
initGrowthRings();
initPointerEffects();
initImpact();
initDrawnStrokes();
initOnView();
initLayerIndex();
initParallax();
