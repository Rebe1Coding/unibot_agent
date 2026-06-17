// Измеряет длительность аудио-Blob через скрытый <audio>. Возвращает секунды или null.

/** Returns audio duration in seconds, or null if it can't be determined. */
export function getAudioDuration(file) {
  return new Promise((resolve) => {
    let url;
    try {
      url = URL.createObjectURL(file);
    } catch {
      resolve(null);
      return;
    }
    const audio = new Audio();
    const done = (value) => {
      URL.revokeObjectURL(url);
      resolve(value);
    };
    audio.addEventListener('loadedmetadata', () => {
      const d = audio.duration;
      // MediaRecorder webm/ogg часто отдаёт Infinity — длительность недостоверна.
      done(Number.isFinite(d) && d > 0 ? d : null);
    });
    audio.addEventListener('error', () => done(null));
    audio.preload = 'metadata';
    audio.src = url;
  });
}
