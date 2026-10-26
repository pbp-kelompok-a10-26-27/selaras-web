// Try-it demos under each landing layer (templates/landing/demos/). They run only in
// the browser and save nothing; "Ulangi" puts each one back to where it started.

const prefersReducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
const numberFormat = new Intl.NumberFormat("id-ID");
const rupiah = (value) => `Rp ${numberFormat.format(value)}`;
const clamp = (value, min, max) => Math.min(Math.max(value, min), max);

function onReset(demo, reset) {
  demo.querySelector("[data-demo-reset]")?.addEventListener("click", reset);
}

// Restarts a CSS animation that is keyed on an attribute
function replay(node, attribute) {
  node.removeAttribute(attribute);
  void node.offsetWidth;
  node.setAttribute(attribute, "");
}

function countTo(node, from, to, format = (v) => numberFormat.format(v)) {
  if (prefersReducedMotion) {
    node.textContent = format(to);
    return;
  }
  const start = performance.now();
  const step = (now) => {
    const progress = Math.min((now - start) / 700, 1);
    node.textContent = format(Math.round(from + (to - from) * (1 - Math.pow(1 - progress, 3))));
    if (progress < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

/* ============================ BELAJAR: fact or myth ============================ */

function initQuiz(demo) {
  const deck = demo.querySelector("[data-quiz-deck]");
  const cards = [...demo.querySelectorAll("[data-quiz-card]")];
  const dots = [...demo.querySelectorAll(".quiz-dot")];
  const answers = demo.querySelector("[data-quiz-answers]");
  const next = demo.querySelector("[data-quiz-next]");
  const end = demo.querySelector("[data-quiz-end]");
  const live = demo.querySelector("[data-quiz-live]");
  let index = 0;
  let score = 0;
  let answered = false;

  // The current card on top, the next two peeking out behind it
  function layout() {
    cards.forEach((card, i) => {
      const place = i - index;
      card.style.setProperty("--stack", String(Math.max(place, 0)));
      card.style.zIndex = String(cards.length - i);
      card.toggleAttribute("data-current", place === 0);
      card.toggleAttribute("data-stack-hidden", place > 2);
      card.toggleAttribute("data-gone", place < 0);
      card.setAttribute("aria-hidden", String(place !== 0));
    });
    dots.forEach((dot, i) => {
      if (i === index) dot.dataset.state = "current";
    });
  }

  function answer(choice) {
    if (answered || index >= cards.length) return;
    answered = true;
    const card = cards[index];
    const right = choice === card.dataset.answer;
    const label = card.dataset.answer === "fakta" ? "fakta" : "mitos";
    if (right) score += 1;

    card.dataset.state = right ? "right" : "wrong";
    card.dataset.choice = choice;
    card.style.setProperty("--drag-x", "0px");
    card.style.setProperty("--lean", "0");
    const verdict = card.querySelector("[data-quiz-verdict]");
    verdict.textContent = right ? `Tepat, ini ${label}.` : `Belum tepat, ini ${label}.`;
    verdict.className = `flex items-center gap-2 font-sans text-sm font-semibold ${right ? "text-primary-800" : "text-tertiary-800"}`;
    dots[index].dataset.state = right ? "right" : "wrong";
    live.textContent = `${verdict.textContent} ${card.querySelector("[data-quiz-result] p:last-child").textContent}`;

    answers.hidden = true;
    next.hidden = false;
    next.querySelector("[data-quiz-next-text]").textContent = index === cards.length - 1 ? "Lihat skor" : "Pernyataan berikutnya";
    next.focus({ preventScroll: true });
  }

  function goNext() {
    const card = cards[index];
    card.style.setProperty("--fly", card.dataset.choice === "fakta" ? "1" : "-1");
    index += 1;
    answered = false;
    layout();
    next.hidden = true;
    if (index < cards.length) {
      answers.hidden = false;
      answers.querySelector("button")?.focus({ preventScroll: true });
      return;
    }
    end.hidden = false;
    end.querySelector("[data-quiz-score]").textContent = score;
    end.querySelector("[data-quiz-message]").textContent =
      score === cards.length
        ? "Sempurna! Anda sudah siap membagikan ilmunya."
        : score >= cards.length / 2
          ? "Bagus! Beberapa hal masih bisa dipelajari bersama."
          : "Tidak apa-apa, justru di sinilah belajar dimulai.";
    live.textContent = `Skor Anda ${score} dari ${cards.length}.`;
  }

  // Drag the top card: right is "fakta", left is "mitos"
  let startX = 0;
  let dragX = 0;
  let dragging = null;
  deck.addEventListener("pointerdown", (event) => {
    const card = event.target.closest("[data-quiz-card][data-current]");
    if (!card || answered || event.button !== 0) return;
    dragging = card;
    startX = event.clientX;
    dragX = 0;
    card.setPointerCapture(event.pointerId);
    card.setAttribute("data-dragging", "");
  });
  deck.addEventListener("pointermove", (event) => {
    if (!dragging) return;
    dragX = event.clientX - startX;
    dragging.style.setProperty("--drag-x", `${dragX}px`);
    dragging.style.setProperty("--lean", String(clamp(dragX / 110, -1, 1)));
  });
  const release = () => {
    if (!dragging) return;
    const card = dragging;
    dragging = null;
    card.removeAttribute("data-dragging");
    if (Math.abs(dragX) > 90) {
      answer(dragX > 0 ? "fakta" : "mitos");
    } else {
      card.style.setProperty("--drag-x", "0px");
      card.style.setProperty("--lean", "0");
    }
  };
  deck.addEventListener("pointerup", release);
  deck.addEventListener("pointercancel", release);

  answers.addEventListener("click", (event) => {
    const button = event.target.closest("[data-quiz-answer]");
    if (button) answer(button.dataset.quizAnswer);
  });
  next.addEventListener("click", goNext);
  demo.addEventListener("keydown", (event) => {
    if (event.key === "ArrowLeft" || event.key === "ArrowRight") {
      if (answered || index >= cards.length) return;
      event.preventDefault();
      answer(event.key === "ArrowRight" ? "fakta" : "mitos");
    }
  });

  onReset(demo, () => {
    index = 0;
    score = 0;
    answered = false;
    cards.forEach((card) => {
      delete card.dataset.state;
      delete card.dataset.choice;
      card.style.setProperty("--drag-x", "0px");
      card.style.setProperty("--lean", "0");
    });
    dots.forEach((dot) => (dot.dataset.state = "todo"));
    end.hidden = true;
    answers.hidden = false;
    next.hidden = true;
    live.textContent = "";
    layout();
  });

  layout();
}

/* ============================ BERTINDAK: 7-day challenge ============================ */

function burstLeaves(container) {
  if (!container || prefersReducedMotion) return;
  for (let i = 0; i < 14; i++) {
    const leaf = document.createElement("span");
    const angle = (i / 14) * Math.PI * 2 + Math.random() * 0.4;
    const distance = 70 + Math.random() * 40;
    leaf.style.setProperty("--x", `${Math.cos(angle) * distance}px`);
    leaf.style.setProperty("--y", `${Math.sin(angle) * distance}px`);
    leaf.style.setProperty("--r", `${Math.random() * 360}deg`);
    container.append(leaf);
    setTimeout(() => leaf.remove(), 1000);
  }
}

function initTracker(demo) {
  const days = [...demo.querySelectorAll("[data-act-day]")];
  const progress = demo.querySelector("[data-act-progress]");
  const count = demo.querySelector("[data-act-count]");
  const message = demo.querySelector("[data-act-message]");
  const badges = [...demo.querySelectorAll("[data-act-badge]")];
  const burst = demo.querySelector("[data-act-burst]");
  const total = days.length;
  let done = 0;

  const encouragement = (n) =>
    ({
      0: "Ketuk Hari 1 untuk mencatat kebiasaan pertama Anda.",
      1: "Hari pertama tercatat. Lencana “Langkah pertama” jadi milik Anda!",
      2: "Dua hari berturut-turut. Satu hari lagi menuju lencana berikutnya.",
      3: "Tiga hari! Lencana “Mulai terbiasa” terbuka.",
      [total - 1]: "Satu hari lagi menuju lencana “Kebiasaan baru”.",
      [total]: "Tantangan selesai! Di SELARAS, lencananya tersimpan di profil Anda.",
    })[n] ?? `${n} hari tercatat. Tinggal ${total - n} hari lagi.`;

  function render(celebrate = false, text = encouragement(done)) {
    days.forEach((button, i) => {
      button.setAttribute("aria-pressed", String(i < done));
      button.toggleAttribute("data-next", i === done);
    });
    progress.style.setProperty("--progress", String((done / total) * 100));
    count.textContent = done;
    badges.forEach((badge) => {
      const unlocked = done >= Number(badge.dataset.actBadge);
      if (celebrate && unlocked && badge.dataset.unlocked === "false") burstLeaves(burst);
      badge.dataset.unlocked = String(unlocked);
    });
    message.textContent = text;
  }

  days.forEach((button) => {
    button.addEventListener("click", () => {
      const day = Number(button.dataset.actDay);
      if (day === done + 1) {
        done = day;
        render(true);
      } else if (day === done) {
        done -= 1;
        render(false, `Catatan Hari ${day} dibatalkan.`);
      } else if (day > done + 1) {
        replay(button, "data-shake");
        render(false, `Satu hari dalam satu waktu: catat Hari ${done + 1} dulu.`);
      } else {
        render(false, `Hari ${day} sudah tercatat. Ketuk Hari ${done} untuk membatalkan catatan terakhir.`);
      }
    });
  });

  onReset(demo, () => {
    done = 0;
    render();
  });
  render(false, message.textContent);
}

/* ============================ BERBAGI: a pretend feed ============================ */

function initFeed(demo) {
  const form = demo.querySelector("[data-share-form]");
  const text = demo.querySelector("[data-share-text]");
  const counter = demo.querySelector("[data-share-count]");
  const submit = demo.querySelector("[data-share-submit]");
  const feed = demo.querySelector("[data-share-feed]");
  const template = demo.querySelector("[data-share-template]");
  const startingFeed = feed.innerHTML;

  function refresh() {
    counter.textContent = `${text.value.length}/${text.maxLength}`;
    submit.disabled = !text.value.trim();
  }

  demo.querySelectorAll("[data-share-prompt]").forEach((chip) => {
    chip.addEventListener("click", () => {
      text.value = chip.dataset.sharePrompt;
      refresh();
      text.focus();
    });
  });
  text.addEventListener("input", refresh);
  // Enter posts, Shift+Enter adds a line
  text.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      form.requestSubmit();
    }
  });

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const message = text.value.trim();
    if (!message) return;
    const post = template.content.firstElementChild.cloneNode(true);
    post.querySelector("[data-post-text]").textContent = message;
    post.setAttribute("data-new", "");
    feed.prepend(post);
    text.value = "";
    refresh();
  });

  function toggle(button, pressed = button.getAttribute("aria-pressed") !== "true") {
    const total = Number(button.dataset.base) + (pressed ? 1 : 0);
    button.setAttribute("aria-pressed", String(pressed));
    const counterNode = button.querySelector("[data-like-count], [data-cheer-count]");
    counterNode.textContent = button.hasAttribute("data-cheer") && !total ? "" : numberFormat.format(total);
  }

  feed.addEventListener("click", (event) => {
    const button = event.target.closest("[data-like], [data-cheer]");
    if (button) toggle(button);
  });
  // Double-tap (or double-click) a post to like it, with a big heart
  feed.addEventListener("dblclick", (event) => {
    const post = event.target.closest("[data-share-post]");
    if (!post || event.target.closest("button")) return;
    toggle(post.querySelector("[data-like]"), true);
    replay(post, "data-popping");
  });

  onReset(demo, () => {
    feed.innerHTML = startingFeed;
    text.value = "";
    refresh();
  });
  refresh();
}

/* ============================ BERDONASI: a pretend donation ============================ */

function initGive(demo) {
  const target = Number(demo.dataset.target);
  const perSeedling = Number(demo.dataset.perSeedling) || 5000;
  const start = { raised: Number(demo.dataset.raised), donors: Number(demo.dataset.donors) };
  let { raised, donors } = start;
  let amount = 25000;

  const form = demo.querySelector("[data-give-form]");
  const range = form.querySelector('input[type="range"]');
  const radios = [...form.querySelectorAll('input[name="amount"]')];
  const amountOut = demo.querySelector("[data-give-amount]");
  const submitText = demo.querySelector("[data-give-submit-text]");
  const bar = demo.querySelector("[data-give-bar]");
  const raisedNode = demo.querySelector("[data-give-raised]");
  const donorsNode = demo.querySelector("[data-give-donors]");
  const percentNode = demo.querySelector("[data-give-percent]");
  const seedlingsNode = demo.querySelector("[data-give-seedlings]");
  const seeds = [...demo.querySelectorAll("[data-give-seed]")];
  const more = demo.querySelector("[data-give-more]");
  const receipt = demo.querySelector("[data-give-receipt]");

  const seedlingsFor = (value) => Math.floor(value / perSeedling);

  function paintBar() {
    const share = (value) => `${(clamp(value, 0, target) / target) * 100}%`;
    bar.style.setProperty("--raised", share(raised));
    // The striped part shows what the chosen amount would add
    bar.style.setProperty("--preview", share(Math.min(amount, target - raised)));
    bar.setAttribute("aria-valuenow", String(Math.min(Math.floor((raised / target) * 100), 100)));
  }

  function setAmount(value, fromRange = false) {
    amount = value;
    if (!fromRange) range.value = String(value);
    radios.forEach((radio) => (radio.checked = Number(radio.value) === value));
    range.style.setProperty("--fill", `${((value - Number(range.min)) / (Number(range.max) - Number(range.min))) * 100}%`);
    amountOut.textContent = rupiah(value);
    submitText.textContent = `Donasi ${rupiah(value)}`;

    const count = seedlingsFor(value);
    seedlingsNode.textContent = numberFormat.format(count);
    seeds.forEach((seed, i) => {
      const on = i < Math.min(count, seeds.length);
      if (on && seed.hasAttribute("data-off")) replay(seed, "data-grow");
      seed.toggleAttribute("data-off", !on);
    });
    more.textContent = count > seeds.length ? `+${numberFormat.format(count - seeds.length)}` : "";
    paintBar();
  }

  radios.forEach((radio) => radio.addEventListener("change", () => setAmount(Number(radio.value))));
  range.addEventListener("input", () => setAmount(Number(range.value), true));

  form.addEventListener("submit", (event) => {
    event.preventDefault();
    const before = raised;
    raised += amount;
    donors += 1;
    countTo(raisedNode, before, raised, rupiah);
    countTo(donorsNode, donors - 1, donors);
    countTo(percentNode, Math.floor((before / target) * 100), Math.floor((raised / target) * 100));
    paintBar();

    receipt.hidden = false;
    replay(receipt, "data-shown");
    const reached = before < target && raised >= target;
    receipt.querySelector("[data-give-receipt-title]").textContent = reached ? "Target tercapai, terima kasih!" : "Terima kasih!";
    receipt.querySelector("[data-give-receipt-text]").textContent =
      `Donasi simulasi ${rupiah(amount)} menanam ${numberFormat.format(seedlingsFor(amount))} bibit mangrove. Tidak ada uang yang ditarik.`;
  });

  onReset(demo, () => {
    ({ raised, donors } = start);
    raisedNode.textContent = rupiah(raised);
    donorsNode.textContent = numberFormat.format(donors);
    percentNode.textContent = Math.floor((raised / target) * 100);
    receipt.hidden = true;
    setAmount(25000);
  });
  setAmount(amount);
}

export function initDemos() {
  const setups = { learn: initQuiz, act: initTracker, share: initFeed, give: initGive };
  document.querySelectorAll("[data-demo]").forEach((demo) => setups[demo.dataset.demo]?.(demo));
}
