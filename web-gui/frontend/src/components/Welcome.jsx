const WELCOME_TEXT =
  'Здравствуйте! Я UniBot — помощник студентов КубГУ. Напишу код, расскажу про ' +
  'преподавателей, помогу с учебниками и предметами — спрашивайте.';

/** Empty-state banner shown before the first message. */
export default function Welcome() {
  return (
    <div className="welcome">
      <pre className="welcome__art" aria-hidden="true">{String.raw`
   __  __      _ ____        __
  / / / /___  (_) __ )____  / /_
 / / / / __ \/ / __  / __ \/ __/
/ /_/ / / / / / /_/ / /_/ / /_
\____/_/ /_/_/_____/\____/\__/`}</pre>
      <p className="welcome__text">
        <span className="welcome__prompt">$</span> {WELCOME_TEXT}
        <span className="cursor" aria-hidden="true" />
      </p>
    </div>
  );
}
