export const PALETTE = [
  "#4FC3F7", "#AED581", "#FFB74D", "#E57373",
  "#BA68C8", "#4DD0E1", "#FFF176", "#F06292",
];

const colorCache = new Map();

export function colorFor(name) {
  if (colorCache.has(name)) return colorCache.get(name);
  let hash = 0;
  for (let i = 0; i < name.length; i++) {
    hash = (hash * 31 + name.charCodeAt(i)) >>> 0;
  }
  const color = PALETTE[hash % PALETTE.length];
  colorCache.set(name, color);
  return color;
}

export function formatTime(iso) {
  if (!iso) return "--:--:--";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  const pad = (n) => String(n).padStart(2, "0");
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function debounce(fn, ms) {
  let t = null;
  return (...args) => {
    if (t) clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

export function escapeHTML(s) {
  return String(s)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}
