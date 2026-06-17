/** Generate a RFC4122-ish UUID, falling back to Math.random when crypto is absent. */
export function generateUuid() {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    const v = c === 'x' ? r : (r & 0x3) | 0x8;
    return v.toString(16);
  });
}

/** Short random hex id for the X-Request-ID header. */
export function generateRequestId() {
  const buf = new Uint8Array(4);
  crypto.getRandomValues(buf);
  return Array.from(buf, (b) => b.toString(16).padStart(2, '0')).join('');
}

const USER_ID_RE = /^[a-zA-Z0-9_-]+$/;

/** Return a valid stored user id or null. */
export function sanitizeUserId(raw) {
  if (typeof raw !== 'string') return null;
  const trimmed = raw.trim();
  if (!trimmed || trimmed.length > 64) return null;
  return USER_ID_RE.test(trimmed) ? trimmed : null;
}

/** Message is non-empty and within the 4096-char backend limit. */
export function isValidMessage(message) {
  if (typeof message !== 'string') return false;
  const trimmed = message.trim();
  return trimmed.length > 0 && trimmed.length <= 4096;
}

/** Human-readable byte size in Russian units. */
export function formatBytes(bytes) {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

/** Promise that resolves after ms milliseconds. */
export function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
