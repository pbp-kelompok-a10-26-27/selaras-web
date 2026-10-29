// "5 menit yang lalu" for <time data-relative datetime="..."> elements. Anything older
// than a week keeps the date the server rendered.
const WEEK = 7 * 24 * 3600;
const UNITS = [
  ["day", 86400],
  ["hour", 3600],
  ["minute", 60],
];
const relativeFormat = new Intl.RelativeTimeFormat("id", { numeric: "auto" });

export function renderRelativeTimes(root = document) {
  root.querySelectorAll("time[data-relative]").forEach((node) => {
    const seconds = (new Date(node.dateTime).getTime() - Date.now()) / 1000;
    if (Number.isNaN(seconds) || -seconds > WEEK) return;

    const [unit, size] = UNITS.find(([, size]) => Math.abs(seconds) >= size) ?? [];
    node.textContent = unit
      ? relativeFormat.format(Math.round(seconds / size), unit)
      : "baru saja";
  });
}
