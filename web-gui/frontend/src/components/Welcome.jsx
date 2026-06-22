import { useEffect, useState } from 'react';

// Короткие сниппеты, которые «печатаются» и стираются в пустом чате.
const SNIPPETS = [
  'print("Привет, КубГУ")',
  'for i in range(5): print(i)',
  'import this',
  'sum(x*x for x in range(8))',
  'def f(x): return x ** 2',
  'data = [n for n in range(10)]',
  'git status',
  'docker compose up -d',
  'uv run pytest -q',
  'pip install requests',
  'ls -la ~/учёба',
  'cat lecture.md | grep TODO',
  'SELECT * FROM dialogs;',
  'npm run build',
];

function useTypewriter(items) {
  const [text, setText] = useState('');

  useEffect(() => {
    let idx = Math.floor(Math.random() * items.length);
    let pos = 0;
    let phase = 'typing';
    let timer;

    const next = () => {
      const full = items[idx];
      if (phase === 'typing') {
        pos += 1;
        setText(full.slice(0, pos));
        if (pos >= full.length) { phase = 'hold'; timer = setTimeout(next, 1200); return; }
        timer = setTimeout(next, 55 + Math.random() * 45);
      } else if (phase === 'hold') {
        phase = 'deleting';
        timer = setTimeout(next, 30);
      } else {
        pos -= 1;
        setText(full.slice(0, pos));
        if (pos <= 0) {
          // следующий сниппет — случайный, но не тот же самый
          let n = Math.floor(Math.random() * items.length);
          if (n === idx) n = (n + 1) % items.length;
          idx = n;
          phase = 'typing';
          timer = setTimeout(next, 450);
          return;
        }
        timer = setTimeout(next, 25);
      }
    };

    timer = setTimeout(next, 400);
    return () => clearTimeout(timer);
  }, [items]);

  return text;
}

/** Empty-state: терминальная заставка с печатающимися сниппетами кода. */
export default function Welcome() {
  const code = useTypewriter(SNIPPETS);
  return (
    <div className="welcome">
      <pre className="welcome__art" aria-hidden="true">{String.raw`
   __  __      _ ____        __
  / / / /___  (_) __ )____  / /_
 / / / / __ \/ / __  / __ \/ __/
/ /_/ / / / / / /_/ / /_/ / /_
\____/_/ /_/_/_____/\____/\__/`}</pre>
      <p className="welcome__text welcome__demo" aria-hidden="true">
        <span className="welcome__prompt">$</span> {code}
        <span className="cursor" />
      </p>
    </div>
  );
}
