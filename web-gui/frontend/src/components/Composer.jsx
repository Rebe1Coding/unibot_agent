import { useEffect, useMemo, useRef, useState } from 'react';
import { ACCEPT_ATTR } from '../lib/uploader.js';
import { formatBytes } from '../lib/utils.js';
import { matchCommands, parseCommand } from '../lib/commands.js';

const MAX_LEN = 4096;

const AttachIcon = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" />
  </svg>
);

const VoiceIcon = () => (
  <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="2">
    <path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" />
    <path d="M19 10v2a7 7 0 0 1-14 0v-2" />
    <line x1="12" y1="19" x2="12" y2="23" />
    <line x1="8" y1="23" x2="16" y2="23" />
  </svg>
);

/** Input row: attachments, attach/voice buttons, auto-growing textarea, send and counter. */
export default function Composer({
  inputRef, enabled, recording, attachments, onSend, onCommand, onFiles, onRemoveAttachment, onToggleVoice,
}) {
  const [text, setText] = useState('');
  const [menuIndex, setMenuIndex] = useState(0);
  const [menuDismissed, setMenuDismissed] = useState(false);
  const fileInputRef = useRef(null);

  useEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 160)}px`;
  }, [text, inputRef]);

  const commandMatches = useMemo(() => (enabled ? matchCommands(text) : []), [enabled, text]);
  const menuOpen = commandMatches.length > 0 && !menuDismissed;

  // Keep the highlighted item in range as the suggestion list shrinks/grows.
  useEffect(() => { setMenuIndex(0); }, [text]);

  const hasText = text.trim().length > 0;
  const canSend = enabled && (hasText || attachments.length > 0);

  const updateText = (value) => {
    setText(value);
    setMenuDismissed(false);
  };

  const runCommand = (name) => {
    setText('');
    setMenuDismissed(false);
    onCommand(name);
  };

  // Pick a suggestion: instant commands fire now; others prefill "<cmd> ".
  const pickCommand = (command) => {
    if (command.instant) {
      runCommand(command.name);
    } else {
      updateText(`${command.name} `);
      if (inputRef.current) inputRef.current.focus();
    }
  };

  const submit = () => {
    const command = parseCommand(text);
    if (command) {
      runCommand(command);
      return;
    }
    if (!canSend) return;
    onSend(text, attachments);
    setText('');
  };

  const onKeyDown = (e) => {
    if (menuOpen) {
      if (e.key === 'ArrowDown') {
        e.preventDefault();
        setMenuIndex((i) => (i + 1) % commandMatches.length);
        return;
      }
      if (e.key === 'ArrowUp') {
        e.preventDefault();
        setMenuIndex((i) => (i - 1 + commandMatches.length) % commandMatches.length);
        return;
      }
      if (e.key === 'Tab' || (e.key === 'Enter' && !e.shiftKey)) {
        e.preventDefault();
        pickCommand(commandMatches[menuIndex] || commandMatches[0]);
        return;
      }
      if (e.key === 'Escape') {
        e.preventDefault();
        setMenuDismissed(true);
        return;
      }
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      submit();
    }
  };

  const onFileChange = (e) => {
    if (e.target.files && e.target.files.length) onFiles(e.target.files);
    e.target.value = '';
  };

  return (
    <form className="composer" autoComplete="off" onSubmit={(e) => { e.preventDefault(); submit(); }}>
      {attachments.length > 0 && (
        <div className="composer__attachments">
          {attachments.map((file, idx) => (
            <span className="attachment-pill" key={idx}>
              {file.name} · {formatBytes(file.size)}
              <button
                type="button"
                className="attachment-pill__remove"
                aria-label={`Убрать ${file.name}`}
                onClick={() => onRemoveAttachment(idx)}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="composer__inputwrap">
        {menuOpen && (
          <ul className="composer__commands" role="listbox" aria-label="Команды">
            {commandMatches.map((command, idx) => (
              <li
                key={command.name}
                role="option"
                aria-selected={idx === menuIndex}
                className={`composer__command${idx === menuIndex ? ' composer__command--active' : ''}`}
                onMouseEnter={() => setMenuIndex(idx)}
                // mousedown (not click) so the textarea doesn't blur before we handle it
                onMouseDown={(e) => { e.preventDefault(); pickCommand(command); }}
              >
                <span className="composer__command-name">{command.name}</span>
                <span className="composer__command-desc">{command.description}</span>
              </li>
            ))}
          </ul>
        )}

        <div className="composer__row">
        <button
          type="button"
          className="composer__icon"
          title="Прикрепить файл"
          aria-label="Прикрепить файл"
          disabled={!enabled}
          onClick={() => fileInputRef.current && fileInputRef.current.click()}
        >
          <AttachIcon />
        </button>
        <input
          ref={fileInputRef}
          type="file"
          hidden
          multiple
          accept={ACCEPT_ATTR}
          onChange={onFileChange}
        />
        <button
          type="button"
          className={`composer__icon${recording ? ' composer__icon--recording' : ''}`}
          title={recording ? 'Остановить запись' : 'Записать голос'}
          aria-label="Записать голос"
          disabled={!enabled}
          onClick={onToggleVoice}
        >
          <VoiceIcon />
        </button>
        <span className="composer__prompt" aria-hidden="true">&gt;</span>
        <textarea
          ref={inputRef}
          className="composer__input"
          rows={1}
          maxLength={MAX_LEN}
          placeholder="Напишите сообщение..."
          aria-label="Сообщение"
          disabled={!enabled}
          value={text}
          onChange={(e) => updateText(e.target.value)}
          onKeyDown={onKeyDown}
        />
        <button type="submit" className="composer__send" aria-label="Отправить" title="Отправить (Enter)" disabled={!canSend && !parseCommand(text)}>
          <span className="composer__send-key" aria-hidden="true">↵</span>
        </button>
        </div>
      </div>

      <div className="composer__footer">
        <span className={`composer__counter${text.length > MAX_LEN ? ' composer__counter--over' : ''}`}>
          {text.length} / {MAX_LEN}
        </span>
      </div>
    </form>
  );
}
