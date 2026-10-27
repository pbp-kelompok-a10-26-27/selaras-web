// Profile picture dialog (templates/accounts/_avatar_modal.html): pick, drop or paste
// a photo, position it inside a circular crop (drag, wheel, pinch, keyboard), then
// send the cropped square to the server. Remove goes through the same dialog.
import { prefersReducedMotion, setButtonLoading } from "./shared.js";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp", "image/gif"];
const OUTPUT_SIZE = 512;
const MAX_ZOOM = 3;
// Space between the stage edge and the circle (matches `inset-3` in the template)
const INSET = 12;
const MODAL_ID = "avatarModal";

const root = document.querySelector("[data-avatar-root]");

if (root) {
  const modal = document.getElementById(MODAL_ID);
  const stage = root.querySelector("[data-avatar-stage]");
  const source = root.querySelector("[data-avatar-source]");
  const zoomInput = root.querySelector("[data-avatar-zoom]");
  const fileInput = root.querySelector("[data-avatar-file]");
  const drop = root.querySelector("[data-avatar-drop]");
  const errorBox = root.querySelector("[data-avatar-error]");
  const errorText = root.querySelector("[data-avatar-error-text]");
  const current = root.querySelector("[data-avatar-current]");
  const currentImage = root.querySelector("[data-avatar-current-image]");
  const previews = [...root.querySelectorAll("[data-avatar-preview]")];
  const saveButton = document.querySelector("[data-avatar-save]");
  const removeButton = root.querySelector("[data-avatar-remove]");
  const steps = {
    pick: root.querySelector('[data-avatar-step="pick"]'),
    edit: root.querySelector('[data-avatar-step="edit"]'),
  };
  const csrfToken = document.querySelector("[name=csrfmiddlewaretoken]")?.value ?? "";

  // The picture being positioned: x/y are the image's top-left corner in stage pixels
  const state = { url: "", width: 0, height: 0, zoom: 1, x: 0, y: 0, busy: false };
  const pointers = new Map();
  let pinchStart = null;
  let frame = 0;

  // ------------------------------- Geometry ------------------------------ //
  const circle = () => stage.clientWidth - INSET * 2;
  const baseScale = () => Math.max(circle() / state.width, circle() / state.height);
  const scale = () => baseScale() * state.zoom;

  // The photo must always cover the circle, so no empty corners can be saved
  function clamp() {
    const s = scale();
    const minX = INSET + circle() - state.width * s;
    const minY = INSET + circle() - state.height * s;
    state.x = Math.min(INSET, Math.max(minX, state.x));
    state.y = Math.min(INSET, Math.max(minY, state.y));
  }

  function setZoom(zoom, anchorX = stage.clientWidth / 2, anchorY = stage.clientHeight / 2) {
    const next = Math.min(MAX_ZOOM, Math.max(1, zoom));
    const before = scale();
    // Keep the point under the anchor where it is while the photo grows
    const imageX = (anchorX - state.x) / before;
    const imageY = (anchorY - state.y) / before;
    state.zoom = next;
    const after = scale();
    state.x = anchorX - imageX * after;
    state.y = anchorY - imageY * after;
    render();
  }

  function centerImage() {
    state.zoom = 1;
    const s = scale();
    state.x = INSET + (circle() - state.width * s) / 2;
    state.y = INSET + (circle() - state.height * s) / 2;
    render();
  }

  // Draws the part of the photo inside the circle onto a canvas of any size
  function drawCrop(canvas) {
    const s = scale();
    const sourceSize = circle() / s;
    const context = canvas.getContext("2d");
    context.imageSmoothingQuality = "high";
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.drawImage(
      source,
      (INSET - state.x) / s,
      (INSET - state.y) / s,
      sourceSize,
      sourceSize,
      0,
      0,
      canvas.width,
      canvas.height,
    );
  }

  function render() {
    clamp();
    source.style.transform = `translate(${state.x}px, ${state.y}px) scale(${scale()})`;
    zoomInput.value = state.zoom;
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => previews.forEach(drawCrop));
  }

  // ------------------------------ UI helpers ----------------------------- //
  function showError(message) {
    errorBox.hidden = !message;
    errorText.textContent = message ?? "";
  }

  function setSaveEnabled(enabled) {
    saveButton.disabled = !enabled;
    saveButton.classList.toggle("pointer-events-none", !enabled);
    saveButton.classList.toggle("cursor-not-allowed", !enabled);
    saveButton.classList.toggle("opacity-45", !enabled);
    saveButton.toggleAttribute("aria-disabled", !enabled);
  }

  function showStep(name) {
    Object.entries(steps).forEach(([key, node]) => {
      node.hidden = key !== name;
    });
    setSaveEnabled(name === "edit");
  }

  function showPicker() {
    if (state.url) URL.revokeObjectURL(state.url);
    state.url = "";
    source.removeAttribute("src");
    fileInput.value = "";
    pointers.clear();
    showError("");
    showStep("pick");
  }

  // Updates every picture of the signed-in user on the page: the hero, the dialog's
  // "current" card, the navbar and (in the dashboard) the sidebar
  function syncAvatars(url) {
    const hero = document.querySelector("[data-avatar-image]");
    const initials = document.querySelector("[data-preview-initials]");
    if (hero) {
      if (url) hero.src = url;
      hero.classList.toggle("hidden", !url);
      initials?.classList.toggle("hidden", Boolean(url));
      if (url && !prefersReducedMotion()) {
        hero.parentElement.classList.remove("avatar-pop");
        void hero.parentElement.offsetWidth; // restart the animation
        hero.parentElement.classList.add("avatar-pop");
      }
    }

    if (url) currentImage.src = url;
    current.classList.toggle("hidden", !url);
    root.dataset.hasAvatar = String(Boolean(url));

    document.querySelectorAll("[data-nav-avatar]").forEach((image) => {
      if (url) image.src = url;
      image.classList.toggle("hidden", !url);
      image.nextElementSibling?.classList.toggle("hidden", Boolean(url));
    });

    document.querySelectorAll("[data-user-avatar]").forEach((holder) => {
      holder.replaceChildren();
      if (url) {
        const image = Object.assign(document.createElement("img"), {
          src: url,
          alt: "",
          className: "h-full w-full object-cover",
        });
        holder.append(image);
      } else {
        holder.textContent = holder.dataset.initials ?? "";
      }
    });
  }

  // ------------------------------ Loading a photo ------------------------ //
  function loadFile(file) {
    showError("");
    if (!file) return;
    if (!ACCEPTED_TYPES.includes(file.type)) {
      showError("That file isn't a JPG, PNG, WebP or GIF image.");
      return;
    }
    const maxMb = Number(root.dataset.maxSourceMb);
    if (file.size > maxMb * 1024 * 1024) {
      showError(`That photo is larger than ${maxMb} MB. Pick a smaller one.`);
      return;
    }

    const url = URL.createObjectURL(file);
    const image = new Image();
    image.onload = () => {
      if (state.url) URL.revokeObjectURL(state.url);
      Object.assign(state, { url, width: image.naturalWidth, height: image.naturalHeight });
      source.src = url;
      source.width = state.width;
      source.height = state.height;
      showStep("edit");
      // The stage only has a size once its step is visible
      requestAnimationFrame(() => {
        centerImage();
        stage.focus({ preventScroll: true });
      });
    };
    image.onerror = () => {
      URL.revokeObjectURL(url);
      showError("We couldn't read that image. Try a different one.");
    };
    image.src = url;
  }

  fileInput.addEventListener("change", () => loadFile(fileInput.files[0]));

  // Drag & drop anywhere on the dialog, highlighting the drop zone while a file is over it
  let dragDepth = 0;
  const hasFiles = (event) => [...(event.dataTransfer?.types ?? [])].includes("Files");

  function setDragging(on) {
    drop.dataset.dragging = String(on);
    drop.querySelector("[data-drop-idle]").hidden = on;
    drop.querySelector("[data-drop-active]").hidden = !on;
  }

  modal.addEventListener("dragenter", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth += 1;
    setDragging(true);
  });
  modal.addEventListener("dragover", (event) => {
    if (hasFiles(event)) event.preventDefault();
  });
  modal.addEventListener("dragleave", () => {
    dragDepth = Math.max(0, dragDepth - 1);
    if (!dragDepth) setDragging(false);
  });
  modal.addEventListener("drop", (event) => {
    if (!hasFiles(event)) return;
    event.preventDefault();
    dragDepth = 0;
    setDragging(false);
    loadFile(event.dataTransfer.files[0]);
  });

  // Paste a screenshot or copied image while the dialog is open
  document.addEventListener("paste", (event) => {
    if (modal.inert || state.busy) return;
    const file = [...(event.clipboardData?.files ?? [])].find((item) =>
      item.type.startsWith("image/"),
    );
    if (file) {
      event.preventDefault();
      loadFile(file);
    }
  });

  // ------------------------------ Positioning ---------------------------- //
  stage.addEventListener("pointerdown", (event) => {
    if (!state.url) return;
    stage.setPointerCapture(event.pointerId);
    pointers.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (pointers.size === 2) {
      const [a, b] = [...pointers.values()];
      pinchStart = { distance: Math.hypot(a.x - b.x, a.y - b.y), zoom: state.zoom };
    }
  });

  stage.addEventListener("pointermove", (event) => {
    const last = pointers.get(event.pointerId);
    if (!last) return;
    const point = { x: event.clientX, y: event.clientY };
    pointers.set(event.pointerId, point);

    if (pointers.size === 2 && pinchStart) {
      const [a, b] = [...pointers.values()];
      const distance = Math.hypot(a.x - b.x, a.y - b.y);
      setZoom(pinchStart.zoom * (distance / pinchStart.distance));
      return;
    }
    state.x += point.x - last.x;
    state.y += point.y - last.y;
    render();
  });

  const endPointer = (event) => {
    pointers.delete(event.pointerId);
    pinchStart = null;
  };
  stage.addEventListener("pointerup", endPointer);
  stage.addEventListener("pointercancel", endPointer);

  stage.addEventListener(
    "wheel",
    (event) => {
      if (!state.url) return;
      event.preventDefault();
      const rect = stage.getBoundingClientRect();
      setZoom(state.zoom * (1 - event.deltaY * 0.0015), event.clientX - rect.left, event.clientY - rect.top);
    },
    { passive: false },
  );

  stage.addEventListener("keydown", (event) => {
    if (!state.url) return;
    const step = event.shiftKey ? 30 : 10;
    const moves = {
      ArrowLeft: [step, 0],
      ArrowRight: [-step, 0],
      ArrowUp: [0, step],
      ArrowDown: [0, -step],
    };
    if (event.key in moves) {
      event.preventDefault();
      state.x += moves[event.key][0];
      state.y += moves[event.key][1];
      render();
    } else if (event.key === "+" || event.key === "=") {
      event.preventDefault();
      setZoom(state.zoom + 0.2);
    } else if (event.key === "-") {
      event.preventDefault();
      setZoom(state.zoom - 0.2);
    } else if (event.key === "0") {
      event.preventDefault();
      centerImage();
    }
  });

  zoomInput.addEventListener("input", () => setZoom(Number(zoomInput.value)));
  root.querySelectorAll("[data-zoom-step]").forEach((button) => {
    button.addEventListener("click", () => setZoom(state.zoom + Number(button.dataset.zoomStep) * 0.25));
  });
  root.querySelector("[data-avatar-reset]").addEventListener("click", centerImage);
  root.querySelector("[data-avatar-back]").addEventListener("click", showPicker);
  window.addEventListener("resize", () => {
    if (state.url && !steps.edit.hidden) centerImage();
  });

  // --------------------------------- Saving ------------------------------ //
  async function send(url, body) {
    const response = await fetch(url, {
      method: "POST",
      headers: { Accept: "application/json", "X-CSRFToken": csrfToken },
      body,
    });
    const isJson = (response.headers.get("content-type") || "").includes("application/json");
    if (!isJson) throw new Error("Your session may have expired. Reload the page and try again.");
    const data = await response.json();
    if (!response.ok) throw new Error(data.error ?? `Something went wrong (${response.status}).`);
    return data;
  }

  function canvasToBlob(canvas) {
    return new Promise((resolve, reject) => {
      canvas.toBlob(
        (blob) => {
          if (!blob) return reject(new Error("We couldn't prepare that photo."));
          // Browsers that can't encode WebP quietly give back a PNG; both are accepted
          resolve(blob);
        },
        "image/webp",
        0.9,
      );
    });
  }

  async function savePhoto() {
    if (state.busy || !state.url) return;
    state.busy = true;
    showError("");
    setButtonLoading(saveButton, true);
    try {
      const canvas = Object.assign(document.createElement("canvas"), {
        width: OUTPUT_SIZE,
        height: OUTPUT_SIZE,
      });
      drawCrop(canvas);
      const blob = await canvasToBlob(canvas);
      const body = new FormData();
      body.append("avatar", blob, "avatar.webp");

      const data = await send(root.dataset.uploadUrl, body);
      syncAvatars(data.avatar_url);
      window.closeModal(MODAL_ID);
      window.showToast?.({
        type: "success",
        title: "Photo updated",
        message: "Your new profile picture is live.",
      });
    } catch (error) {
      showError(error.message);
    } finally {
      state.busy = false;
      setButtonLoading(saveButton, false);
      // setButtonLoading disables the button; restore the right state for the step
      setSaveEnabled(!steps.edit.hidden);
    }
  }

  async function removePhoto() {
    if (state.busy) return;
    state.busy = true;
    showError("");
    setButtonLoading(removeButton, true);
    try {
      await send(root.dataset.removeUrl, new FormData());
      syncAvatars("");
      window.closeModal(MODAL_ID);
      window.showToast?.({
        type: "success",
        title: "Photo removed",
        message: "You're back to your initials.",
      });
    } catch (error) {
      showError(error.message);
    } finally {
      state.busy = false;
      setButtonLoading(removeButton, false);
    }
  }

  saveButton.addEventListener("click", savePhoto);
  removeButton?.addEventListener("click", removePhoto);

  // Enter saves from the crop area
  stage.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && state.url) {
      event.preventDefault();
      savePhoto();
    }
  });

  // Every visit starts from the picker, with nothing left from last time
  modal.addEventListener("modal:close", () => {
    setTimeout(showPicker, 300);
    setDragging(false);
    dragDepth = 0;
  });

  showPicker();
}
