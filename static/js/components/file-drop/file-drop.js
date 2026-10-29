// File drop component: drag and drop, thumbnail preview and client-side size / type check.
// The server validates again; this only saves a round trip.
(function () {
  const ERROR_CLASS =
    "flex items-center gap-1.5 font-sans text-xs font-semibold text-tertiary-700";

  function formatSize(bytes) {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} KB`;
    return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  }

  function matchesAccept(file, accept) {
    if (!accept) return true;
    const name = file.name.toLowerCase();
    return accept
      .split(",")
      .map((rule) => rule.trim().toLowerCase())
      .some((rule) => {
        if (rule.startsWith(".")) return name.endsWith(rule);
        if (rule.endsWith("/*")) return file.type.startsWith(rule.slice(0, -1));
        return file.type === rule;
      });
  }

  function initDrop(root) {
    if (root.dataset.ready) return;
    root.dataset.ready = "true";

    const input = root.querySelector('input[type="file"]');
    const zone = root.querySelector("[data-file-zone]");
    const preview = root.querySelector("[data-file-preview]");
    const thumb = root.querySelector("[data-file-thumb]");
    const icon = root.querySelector("[data-file-icon]");
    const nameEl = root.querySelector("[data-file-name]");
    const sizeEl = root.querySelector("[data-file-size]");
    const errorEl = root.querySelector("[data-file-error]");
    const maxBytes = (Number(root.dataset.maxMb) || 0) * 1024 * 1024;
    const accept = root.dataset.accept || "";
    let objectUrl = null;

    function showError(message) {
      errorEl.replaceChildren();
      if (!message) return;
      const line = document.createElement("p");
      line.className = ERROR_CLASS;
      line.textContent = message;
      errorEl.append(line);
    }

    function reset() {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      objectUrl = null;
      thumb.querySelector("img")?.remove();
      icon.hidden = false;
      preview.hidden = true;
      zone.hidden = false;
    }

    function clear() {
      input.value = "";
      reset();
    }

    function accept_(file) {
      if (!matchesAccept(file, accept)) {
        showError("Format file tidak didukung.");
        return false;
      }
      if (maxBytes && file.size > maxBytes) {
        showError(`Ukuran file maksimal ${root.dataset.maxMb} MB.`);
        return false;
      }
      return true;
    }

    function show(file) {
      showError("");
      if (!file) return reset();
      if (!accept_(file)) return clear();

      reset();
      nameEl.textContent = file.name;
      sizeEl.textContent = formatSize(file.size);

      if (file.type.startsWith("image/")) {
        objectUrl = URL.createObjectURL(file);
        const img = document.createElement("img");
        img.src = objectUrl;
        img.alt = "";
        img.className = "h-full w-full object-cover";
        icon.hidden = true;
        thumb.append(img);
      }
      preview.hidden = false;
      zone.hidden = true;
      preview.classList.add("attach-tile-in");
    }

    input.addEventListener("change", () => show(input.files[0]));
    root.querySelector("[data-file-clear]").addEventListener("click", () => {
      clear();
      showError("");
      input.focus();
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
      const [file] = event.dataTransfer?.files ?? [];
      if (!file) return;
      try {
        input.files = event.dataTransfer.files;
      } catch {
        return;
      }
      show(file);
    });

    // A form that was reset or came back with errors may already hold a file
    if (input.files[0]) show(input.files[0]);
  }

  window.initFileDrops = (scope = document) =>
    scope.querySelectorAll("[data-file-drop]").forEach(initDrop);

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.initFileDrops());
  } else {
    window.initFileDrops();
  }
})();
