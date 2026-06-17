/** Wraps MediaRecorder to capture a single voice clip as a Blob. */
export class VoiceRecorder {
  constructor() {
    this._recorder = null;
    this._chunks = [];
    this._stream = null;
    this._mimeType = null;
    this._startedAt = 0;
    this._durationSec = 0;
  }

  get isRecording() {
    return this._recorder != null && this._recorder.state === 'recording';
  }

  /** Length of the last finished recording, in seconds. */
  get durationSec() {
    return this._durationSec;
  }

  /** Request the mic and begin recording. */
  async start() {
    if (this.isRecording) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('Запись голоса не поддерживается браузером');
    }
    this._stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this._mimeType = this._pickMimeType();
    this._chunks = [];
    this._recorder = new MediaRecorder(
      this._stream,
      this._mimeType ? { mimeType: this._mimeType } : undefined,
    );
    this._recorder.addEventListener('dataavailable', (e) => {
      if (e.data && e.data.size > 0) this._chunks.push(e.data);
    });
    this._recorder.start();
    this._startedAt = Date.now();
  }

  /** Stop recording and return the captured Blob. */
  async stop() {
    if (!this._recorder) return null;
    const done = new Promise((resolve) => {
      this._recorder.addEventListener('stop', () => resolve(), { once: true });
    });
    this._recorder.stop();
    await done;
    this._durationSec = (Date.now() - this._startedAt) / 1000;
    const blob = new Blob(this._chunks, { type: this._mimeType || 'audio/webm' });
    this._cleanup();
    return blob;
  }

  /** Abort recording and release the mic without producing a Blob. */
  cancel() {
    if (this._recorder && this._recorder.state !== 'inactive') {
      try { this._recorder.stop(); } catch { /* already stopped */ }
    }
    this._cleanup();
  }

  _cleanup() {
    if (this._stream) {
      this._stream.getTracks().forEach((t) => t.stop());
      this._stream = null;
    }
    this._recorder = null;
    this._chunks = [];
  }

  _pickMimeType() {
    // Предпочитаем форматы, которые модель принимает напрямую (на случай, если ffmpeg-конвертация недоступна).
    const candidates = ['audio/ogg;codecs=opus', 'audio/mp4', 'audio/webm;codecs=opus', 'audio/webm'];
    if (typeof MediaRecorder === 'undefined') return null;
    for (const m of candidates) {
      if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(m)) return m;
    }
    return null;
  }
}
