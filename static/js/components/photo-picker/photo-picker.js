// Photo picker component: several photos for one <input type="file" multiple>.
// Keeps the chosen files in a DataTransfer so they can be removed and reordered, shrinks
// big photos in the browser (longest side 2048px, JPEG) so a set of phone photos fits the
// upload limit, and shows a count / total size meter. The server validates again.
(function () {
  const MAX_SIDE = 2048;
  const SHRINK_OVER = 1.2 * 1024 * 1024;
  const ERROR_CLASS =
    "flex items-center gap-1.5 font-sans text-xs font-semibold text-tertiary-700";

  function formatSize(bytes) {
    if (bytes < 1024 * 1024) return `${Math.max(1, Math.round(bytes / 1024))} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function loadImage(file) {
    return new Promise((resolve, reject) => {
      const url = URL.createObjectURL(file);
      const img = new Image();
      img.onload = () => resolve({ img, url });
      img.onerror = () => {
        URL.revokeObjectURL(url);
        reject(new Error("unreadable"));
      };
      img.src = url;
    });
  }

  // Large photos are redrawn smaller as JPEG; small ones are kept untouched
  async function shrink(file) {
    if (file.size <= SHRINK_OVER) return file;
    try {
      const { img, url } = await loadImage(file);
      const scale = Math.min(1, MAX_SIDE / Math.max(img.naturalWidth, img.naturalHeight));
      const canvas = document.createElement("canvas");
      canvas.width = Math.round(img.naturalWidth * scale);
      canvas.height = Math.round(img.naturalHeight * scale);
      const context = canvas.getContext("2d");
      context.fillStyle = "#fff";
      context.fillRect(0, 0, canvas.width, canvas.height);
      context.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      const blob = await new Promise((resolve) => canvas.toBlob(resolve, "image/jpeg", 0.85));
      if (!blob || blob.size >= file.size) return file;
      const name = file.name.replace(/\.[^.]+$/, "") + ".jpg";
      return new File([blob], name, { type: "image/jpeg", lastModified: Date.now() });
    } catch {
      return file;
    }
  }

  function initPicker(root) {
    if (root.dataset.ready) return;
    root.dataset.ready = "true";

    const input = root.querySelector('input[type="file"]');
    const zone = root.querySelector("[data-photo-zone]");
    const list = root.querySelector("[data-photo-list]");
    const template = root.querySelector("[data-photo-template]");
    const meter = root.querySelector("[data-photo-meter]");
    const bar = root.querySelector("[data-photo-meter-bar]");
    const countEl = root.querySelector("[data-photo-count]");
    const errorEl = root.querySelector("[data-photo-error]");
    const maxFiles = Number(root.dataset.maxFiles) || 10;
    const maxBytes = (Number(root.dataset.maxMb) || 10) * 1024 * 1024;
    const accepted = (root.dataset.accept || "").split(",").map((type) => type.trim());
    let files = [];
    const urls = new Map();

    function showError(message) {
      errorEl.replaceChildren();
      if (!message) return;
      const line = document.createElement("p");
      line.className = ERROR_CLASS;
      line.textContent = message;
      errorEl.append(line);
    }

    const totalBytes = () => files.reduce((sum, file) => sum + file.size, 0);

    function sync() {
      const transfer = new DataTransfer();
      files.forEach((file) => transfer.items.add(file));
      input.files = transfer.files;
      render();
      root.dispatchEvent(new CustomEvent("photos:change", { bubbles: true, detail: { files } }));
    }

    function render() {
      list.replaceChildren();
      files.forEach((file, index) => {
        const item = template.content.firstElementChild.cloneNode(true);
        if (!urls.has(file)) urls.set(file, URL.createObjectURL(file));
        item.querySelector("[data-photo-img]").src = urls.get(file);
        item.querySelector("[data-photo-index]").textContent = String(index + 1);
        const left = item.querySelector("[data-photo-left]");
        left.disabled = index === 0;
        left.addEventListener("click", () => {
          [files[index - 1], files[index]] = [files[index], files[index - 1]];
          sync();
          list.children[index - 1]?.querySelector("[data-photo-left]")?.focus();
        });
        item.querySelector("[data-photo-remove]").addEventListener("click", () => {
          URL.revokeObjectURL(urls.get(file));
          urls.delete(file);
          files.splice(index, 1);
          showError("");
          sync();
          (list.children[index] || list.children[index - 1])
            ?.querySelector("[data-photo-remove]")
            ?.focus();
          if (!files.length) input.focus();
        });
        list.append(item);
      });

      const total = totalBytes();
      meter.hidden = files.length === 0;
      bar.style.width = `${Math.min(100, (total / maxBytes) * 100)}%`;
      bar.dataset.warn = String(total > maxBytes * 0.9);
      countEl.textContent = `${files.length}/${maxFiles} foto · ${formatSize(total)} dari ${formatSize(maxBytes)}`;
      zone.dataset.full = String(files.length >= maxFiles);
    }

    async function add(incoming) {
      showError("");
      const images = [...incoming].filter((file) => accepted.includes(file.type));
      if (images.length < incoming.length) {
        showError("Sebagian file dilewati: gunakan JPEG, PNG, atau WebP.");
      }
      const room = maxFiles - files.length;
      if (images.length > room) {
        showError(`Maksimal ${maxFiles} foto per postingan.`);
      }
      zone.setAttribute("aria-busy", "true");
      for (const file of images.slice(0, Math.max(room, 0))) {
        const ready = await shrink(file);
        if (totalBytes() + ready.size > maxBytes) {
          showError(`Total ukuran foto maksimal ${formatSize(maxBytes)}. Sebagian foto tidak ditambahkan.`);
          break;
        }
        files.push(ready);
      }
      zone.removeAttribute("aria-busy");
      sync();
    }

    input.addEventListener("change", () => {
      // The input now holds only the new selection; merge it into the list
      const picked = [...input.files].filter((file) => !files.includes(file));
      add(picked);
    });

    ["dragenter", "dragover"].forEach((type) =>
      zone.addEventListener(type, (event) => {
        event.preventDefault();
        zone.dataset.dragging = "true";
      }),
    );
    ["dragleave", "dragend"].forEach((type) =>
      zone.addEventListener(type, () => delete zone.dataset.dragging),
    );
    zone.addEventListener("drop", (event) => {
      event.preventDefault();
      delete zone.dataset.dragging;
      if (event.dataTransfer?.files?.length) add(event.dataTransfer.files);
    });

    // Paste a screenshot straight into the form
    root.closest("form")?.addEventListener("paste", (event) => {
      const pasted = [...(event.clipboardData?.files ?? [])];
      if (pasted.length) add(pasted);
    });

    root.closest("form")?.addEventListener("reset", () => {
      urls.forEach((url) => URL.revokeObjectURL(url));
      urls.clear();
      files = [];
      setTimeout(sync, 0);
    });
  }

  window.initPhotoPickers = (scope = document) =>
    scope.querySelectorAll("[data-photo-picker]").forEach(initPicker);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.initPhotoPickers());
  } else {
    window.initPhotoPickers();
  }
})();
