import { generateRequestId } from '../lib/utils.js';

/** Parse one SSE frame ("data: {...}") into an object, or null if malformed. */
function parseSseFrame(frame) {
  const data = frame
    .split('\n')
    .filter((line) => line.startsWith('data:'))
    .map((line) => line.slice(5).trimStart())
    .join('\n');
  if (!data) return null;
  try { return JSON.parse(data); } catch { return null; }
}

/** Non-2xx HTTP response from the backend. */
export class ApiError extends Error {
  constructor(status, payload) {
    super(`API ${status}`);
    this.status = status;
    this.payload = payload;
  }
}

/** Request aborted because it exceeded the configured timeout. */
export class TimeoutError extends Error {
  constructor() {
    super('Timeout');
    this.name = 'TimeoutError';
  }
}

/** Thin client over the FastAPI proxy endpoints (/auth, /api/chat, /api/dialogs, /api/voice, /health). */
export class ApiClient {
  constructor({ baseUrl = '/', timeoutMs = 120_000 } = {}) {
    this.baseUrl = baseUrl;
    this.timeoutMs = timeoutMs;
  }

  /** GET /auth/me — current authenticated user, or null if not logged in. */
  async me() {
    try {
      return await this._json('GET', 'auth/me');
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) return null;
      throw err;
    }
  }

  /** POST /auth/logout — clear the session cookie. */
  async logout() {
    return this._json('POST', 'auth/logout');
  }

  /** GET /api/dialogs — list the user's dialogs. */
  async listDialogs() {
    return this._json('GET', 'api/dialogs');
  }

  /** POST /api/dialogs — start a new dialog; archives the previous one. */
  async newDialog(previousDialogId = null) {
    return this._json('POST', 'api/dialogs', { previous_dialog_id: previousDialogId });
  }

  /** GET /api/dialogs/{id} — message log of a dialog. */
  async dialogHistory(dialogId) {
    return this._json('GET', `api/dialogs/${encodeURIComponent(dialogId)}`);
  }

  /** DELETE /api/dialogs/{id} — remove a dialog. */
  async deleteDialog(dialogId) {
    return this._json('DELETE', `api/dialogs/${encodeURIComponent(dialogId)}`);
  }

  /** POST /api/chat — main ReAct pipeline. */
  async chat({ dialogId, message, clarificationResponse = null }) {
    return this._json('POST', 'api/chat', {
      dialog_id: dialogId,
      message,
      clarification_response: clarificationResponse,
    });
  }

  /**
   * POST /api/chat/stream — same pipeline as chat(), streamed via Server-Sent Events.
   * Calls onEvent(parsed) for each event; resolves when the stream ends.
   */
  async chatStream({ dialogId, message, clarificationResponse = null, onEvent }) {
    const controller = new AbortController();
    let timer;
    const resetIdle = () => {
      clearTimeout(timer);
      timer = setTimeout(() => controller.abort(), this.timeoutMs);
    };
    resetIdle();
    try {
      const res = await fetch(`${this.baseUrl}api/chat/stream`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-Request-ID': generateRequestId() },
        body: JSON.stringify({
          dialog_id: dialogId,
          message,
          clarification_response: clarificationResponse,
        }),
        signal: controller.signal,
      });
      if (!res.ok || !res.body) {
        let payload = null;
        try { payload = await res.json(); } catch { payload = null; }
        throw new ApiError(res.status, payload);
      }
      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        resetIdle();
        buffer += decoder.decode(value, { stream: true });
        let idx;
        while ((idx = buffer.indexOf('\n\n')) !== -1) {
          const event = parseSseFrame(buffer.slice(0, idx));
          buffer = buffer.slice(idx + 2);
          if (event) onEvent(event);
        }
      }
    } catch (err) {
      if (err.name === 'AbortError') throw new TimeoutError();
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  /** GET /api/voice/{taskId} — transcription task status. */
  async voiceStatus(taskId) {
    return this._json('GET', `api/voice/${encodeURIComponent(taskId)}`);
  }

  /** GET /health — upstream services status. */
  async health() {
    return this._json('GET', 'health');
  }

  /** POST /api/voice — upload audio for async transcription. mode: "command" | "lecture". */
  async voice({ file, mode = 'command' }) {
    const url = `${this.baseUrl}api/voice?mode=${encodeURIComponent(mode)}`;
    const form = new FormData();
    form.append('file', file, file.name);
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const res = await fetch(url, {
        method: 'POST',
        body: form,
        headers: { 'X-Request-ID': generateRequestId() },
        signal: controller.signal,
      });
      return await this._parse(res);
    } catch (err) {
      if (err.name === 'AbortError') throw new TimeoutError();
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  async _json(method, path, body) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    const init = {
      method,
      headers: { 'X-Request-ID': generateRequestId() },
      signal: controller.signal,
    };
    if (body !== undefined && body !== null) {
      init.headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
    try {
      const res = await fetch(`${this.baseUrl}${path}`, init);
      return await this._parse(res);
    } catch (err) {
      if (err.name === 'AbortError') throw new TimeoutError();
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  async _parse(res) {
    let payload = null;
    const ctype = res.headers.get('content-type') || '';
    if (ctype.includes('application/json')) {
      try { payload = await res.json(); } catch { payload = null; }
    } else {
      try { payload = await res.text(); } catch { payload = null; }
    }
    if (!res.ok) throw new ApiError(res.status, payload);
    return payload;
  }
}
