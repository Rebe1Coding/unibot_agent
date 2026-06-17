import { useState } from 'react';

/** Clarification option buttons; interactive only for the latest unanswered message. */
export default function Clarification({ options, interactive, answered, onPick }) {
  const [otherOpen, setOtherOpen] = useState(false);
  const [otherText, setOtherText] = useState('');

  const submitOther = (opt) => {
    const text = otherText.trim();
    if (!text) return;
    onPick({ ...opt, value: text });
  };

  return (
    <div className="clarification">
      {options.map((opt, i) => {
        const selected = answered === opt.label;
        // «Свой вариант» раскрывает поле свободного ввода.
        if (opt.free_text) {
          if (otherOpen && interactive) {
            return (
              <div className="clarification__other" key={i}>
                <input
                  type="text"
                  className="clarification__input"
                  placeholder="Ваш вариант ответа…"
                  value={otherText}
                  autoFocus
                  onChange={(e) => setOtherText(e.target.value)}
                  onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); submitOther(opt); } }}
                />
                <button
                  type="button"
                  className="clarification__btn"
                  disabled={!otherText.trim()}
                  onClick={() => submitOther(opt)}
                >
                  Отправить
                </button>
              </div>
            );
          }
          return (
            <button
              key={i}
              type="button"
              className={`clarification__btn${selected ? ' clarification__btn--selected' : ''}`}
              disabled={!interactive}
              onClick={() => setOtherOpen(true)}
            >
              {opt.label}
            </button>
          );
        }
        return (
          <button
            key={i}
            type="button"
            className={`clarification__btn${selected ? ' clarification__btn--selected' : ''}`}
            disabled={!interactive}
            onClick={() => onPick(opt)}
          >
            {opt.label}
          </button>
        );
      })}
    </div>
  );
}
