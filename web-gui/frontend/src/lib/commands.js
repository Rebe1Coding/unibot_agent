// Slash-command registry for the composer, Telegram-style.
// `instant` commands run immediately on pick; others would prefill the input.

export const COMMANDS = [
  { name: '/new', description: 'Начать новый чат', instant: true },
  { name: '/status', description: 'Статус распознавания лекции', instant: true },
];

/** Commands to suggest while typing: only when the text is a bare "/word" (no space yet). */
export function matchCommands(text) {
  if (!/^\/\S*$/.test(text)) return [];
  const q = text.toLowerCase();
  return COMMANDS.filter((c) => c.name.startsWith(q));
}

/** If the submitted text is a known command (with or without trailing args), return its name. */
export function parseCommand(text) {
  const trimmed = (text || '').trim();
  const found = COMMANDS.find((c) => trimmed === c.name || trimmed.startsWith(`${c.name} `));
  return found ? found.name : null;
}
