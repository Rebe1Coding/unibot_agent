/** Terminal title bar with window dots, session path and an optional status banner. */
export default function Header({ banner }) {
  return (
    <header className="chat__header">
      <div className="chat__titlebar">
        <span className="chat__dots" aria-hidden="true">
          <i /><i /><i />
        </span>
        <span className="chat__path">студент@unibot:~/помощник-кубгу</span>
      </div>
      {banner && (
        <div className={`banner banner--${banner.variant}`} role="status">
          {banner.text}
        </div>
      )}
    </header>
  );
}
