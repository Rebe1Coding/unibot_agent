import { ContainerList } from "./containers.js";
import { LogStream } from "./logs.js";
import { debounce } from "./utils.js";

const STATE_LABELS = {
  IDLE: "● IDLE",
  LOADING_HISTORY: "● Loading...",
  STREAMING: "● Live",
  PAUSED: "● Paused",
  DISCONNECTED: "● Disconnected",
  ERROR: "● Error",
};

const STATE_CLASSES = {
  IDLE: "idle",
  LOADING_HISTORY: "loading",
  STREAMING: "streaming",
  PAUSED: "paused",
  DISCONNECTED: "disconnected",
  ERROR: "error",
};

function $(id) { return document.getElementById(id); }

function applyState(state) {
  const dot = document.querySelector(".dot");
  const text = document.querySelector(".status__text");
  const footer = $("footer-state");
  const cls = STATE_CLASSES[state] || "idle";
  if (dot) dot.className = `dot dot--${cls}`;
  if (text) text.textContent = state;
  if (footer) {
    footer.className = `state state--${cls}`;
    footer.textContent = STATE_LABELS[state] || state;
  }
}

function startClock() {
  const el = $("clock");
  if (!el) return;
  const tick = () => {
    const d = new Date();
    const p = (n) => String(n).padStart(2, "0");
    el.textContent = `${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
  };
  tick();
  setInterval(tick, 1000);
}

function setupSidebarToggle() {
  const sidebar = $("sidebar");
  const toggle = $("sidebar-toggle");
  if (!toggle) return;
  toggle.addEventListener("click", () => sidebar.classList.toggle("open"));
}

document.addEventListener("DOMContentLoaded", () => {
  startClock();
  setupSidebarToggle();
  applyState("IDLE");

  const startBtn = $("start-btn");
  const stopBtn = $("stop-btn");
  const clearBtn = $("clear-btn");
  const tailInput = $("tail-input");
  const search = $("log-search");

  const logs = new LogStream({
    viewportEl: $("viewport"),
    outputEl: $("output"),
    placeholderEl: $("placeholder"),
    countEl: $("lines-counter"),
    resumeBtnEl: $("resume-btn"),
    onState: applyState,
  });

  const list = new ContainerList($("container-list"), $("select-all"), (selected) => {
    startBtn.disabled = selected.size === 0;
  });

  list.load();

  $("refresh-btn").addEventListener("click", () => list.load());

  startBtn.addEventListener("click", () => {
    const selected = Array.from(list.selected);
    if (!selected.length) return;
    const tail = Math.max(0, Math.min(10000, parseInt(tailInput.value || "200", 10)));
    logs.start(selected, tail);
    stopBtn.disabled = false;
    startBtn.disabled = true;
  });

  stopBtn.addEventListener("click", () => {
    logs.stop();
    stopBtn.disabled = true;
    startBtn.disabled = list.selected.size === 0;
  });

  clearBtn.addEventListener("click", () => logs.clear());

  search.addEventListener("input", debounce((e) => logs.setFilter(e.target.value), 150));
});
