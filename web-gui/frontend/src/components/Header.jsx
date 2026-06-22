/** Terminal title bar with window dots, session path and an optional status banner. */
export default function Header({ banner, onMenu }) {
  return (
    <header className="chat__header">
      <div className="chat__titlebar">
        <button type="button" className="chat__menu" aria-label="Открыть меню" onClick={onMenu}>
          <span /><span /><span />
        </button>
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
