import { buildStreamUrl } from "./api.js";
import { colorFor, formatTime, escapeHTML } from "./utils.js";

const MAX_BUFFER = 5000;

export class LogStream {
  constructor({ viewportEl, outputEl, placeholderEl, countEl, resumeBtnEl, onState }) {
    this.viewport = viewportEl;
    this.output = outputEl;
    this.placeholder = placeholderEl;
    this.counter = countEl;
    this.resumeBtn = resumeBtnEl;
    this.onState = onState;

    this.source = null;
    this.containers = [];
    this.tail = 200;
    this.lines = 0;
    this.autoScroll = true;
    this.filter = "";

    this.viewport.addEventListener("scroll", () => this._onScroll());
    this.resumeBtn.addEventListener("click", () => this.resumeAutoScroll());
  }

  start(containers, tail) {
    this.stop();
    if (!containers.length) return;
    this.containers = containers;
    this.tail = tail;
    this.placeholder.hidden = true;
    this.output.hidden = false;
    this._setState("LOADING_HISTORY");

    const url = buildStreamUrl(containers, tail);
    const source = new EventSource(url);
    this.source = source;

    source.addEventListener("ready", () => this._setState("STREAMING"));

    source.addEventListener("log", (e) => {
      try { this._appendLog(JSON.parse(e.data)); } catch {}
    });

    source.addEventListener("heartbeat", () => {
      if (this._state !== "PAUSED") this._setState("STREAMING");
    });

    source.addEventListener("error", (e) => {
      if (source.readyState === EventSource.CLOSED) {
        this._setState("DISCONNECTED");
        return;
      }
      if (e.data) {
        try {
          const payload = JSON.parse(e.data);
          this._appendError(payload.container || "?", payload.error || "stream error");
        } catch {}
      }
    });

    source.onerror = () => {
      if (source.readyState === EventSource.CLOSED) {
        this._setState("DISCONNECTED");
      } else {
        this._setState("DISCONNECTED");
      }
    };
  }

  stop() {
    if (this.source) {
      this.source.close();
      this.source = null;
    }
    this._setState("IDLE");
  }

  clear() {
    this.output.innerHTML = "";
    this.lines = 0;
    this._updateCounter();
    if (!this.source) {
      this.output.hidden = true;
      this.placeholder.hidden = false;
    }
  }

  setFilter(query) {
    this.filter = (query || "").toLowerCase();
    const rows = this.output.children;
    for (const row of rows) this._applyFilter(row);
  }

  resumeAutoScroll() {
    this.autoScroll = true;
    this.resumeBtn.classList.add("btn--hidden");
    this._scrollToBottom();
    if (this.source) this._setState("STREAMING");
  }

  _appendLog(payload) {
    const { ts, container, stream, text } = payload;
    const row = document.createElement("div");
    row.className = `log-line log-line--${stream}`;
    const safeText = this.filter
      ? this._highlight(text, this.filter)
      : escapeHTML(text);
    row.innerHTML = `
      <span class="log-line__ts">[${formatTime(ts)}]</span>
      <span class="log-line__container" style="color:${colorFor(container)}">[${escapeHTML(container)}]</span>
      <span class="log-line__text">${safeText}</span>
    `;
    this._applyFilter(row);
    this.output.appendChild(row);
    this.lines++;
    this._trim();
    this._updateCounter();
    if (this.autoScroll) this._scrollToBottom();
  }

  _appendError(container, error) {
    const row = document.createElement("div");
    row.className = "log-line log-line--error";
    row.innerHTML = `
      <span class="log-line__ts">[${formatTime(new Date().toISOString())}]</span>
      <span class="log-line__container" style="color:${colorFor(container)}">[${escapeHTML(container)}]</span>
      <span class="log-line__text">⚠ ${escapeHTML(error)}</span>
    `;
    this.output.appendChild(row);
    this.lines++;
    this._trim();
    this._updateCounter();
    if (this.autoScroll) this._scrollToBottom();
  }

  _highlight(text, needle) {
    const safe = escapeHTML(text);
    if (!needle) return safe;
    const lower = safe.toLowerCase();
    const idx = lower.indexOf(needle);
    if (idx < 0) return safe;
    return (
      safe.slice(0, idx) +
      `<span class="log-line__highlight">${safe.slice(idx, idx + needle.length)}</span>` +
      safe.slice(idx + needle.length)
    );
  }

  _applyFilter(row) {
    if (!this.filter) {
      row.classList.remove("hidden");
      return;
    }
    const text = row.textContent.toLowerCase();
    row.classList.toggle("hidden", !text.includes(this.filter));
  }

  _trim() {
    while (this.lines > MAX_BUFFER && this.output.firstChild) {
      this.output.removeChild(this.output.firstChild);
      this.lines--;
    }
  }

  _updateCounter() {
    this.counter.textContent = `${this.lines} строк`;
  }

  _scrollToBottom() {
    this.viewport.scrollTop = this.viewport.scrollHeight;
  }

  _onScroll() {
    const nearBottom =
      this.viewport.scrollHeight - this.viewport.scrollTop - this.viewport.clientHeight < 40;
    if (nearBottom) {
      if (!this.autoScroll) {
        this.autoScroll = true;
        this.resumeBtn.classList.add("btn--hidden");
        if (this.source) this._setState("STREAMING");
      }
    } else if (this.autoScroll) {
      this.autoScroll = false;
      this.resumeBtn.classList.remove("btn--hidden");
      if (this.source) this._setState("PAUSED");
    }
  }

  _setState(state) {
    this._state = state;
    this.onState(state);
  }
}
