const ALLOWED_EXT = new Set([
  'docx', 'xlsx', 'csv', 'md', 'txt',
  'png', 'jpg', 'jpeg', 'gif', 'webp', 'svg', 'bmp',
  'ogg', 'mp3', 'wav', 'webm', 'm4a',
]);

const AUDIO_EXT = new Set(['ogg', 'mp3', 'wav', 'webm', 'm4a']);

const MAX_SIZE_BYTES = 50 * 1024 * 1024;

const ACCEPT_ATTR =
  '.docx,.xlsx,.csv,.md,.txt,image/*,audio/ogg,audio/mpeg,audio/wav,audio/x-wav,audio/mp3';

export { ACCEPT_ATTR };

function ext(file) {
  return (file.name.split('.').pop() || '').toLowerCase();
}

/** True for audio files (by extension or MIME type). */
export function isAudio(file) {
  return AUDIO_EXT.has(ext(file)) || (file.type || '').startsWith('audio/');
}

/** Split a FileList into accepted files and rejected ones with reasons. */
export function validateFiles(fileList) {
  const accepted = [];
  const rejected = [];
  for (const file of fileList) {
    const e = ext(file);
    if (!ALLOWED_EXT.has(e)) {
      rejected.push({ file, reason: `Формат .${e} не поддерживается` });
      continue;
    }
    if (file.size > MAX_SIZE_BYTES) {
      rejected.push({ file, reason: `${file.name} больше 50 МБ` });
      continue;
    }
    accepted.push(file);
  }
  return { accepted, rejected };
}
