/** Left panel: logo, dialog list, new chat, and the signed-in user with logout. */
export default function Sidebar({ dialogs, activeId, onNewChat, onSelect, onDelete, user, onLogout, open, onClose }) {
  return (
    <>
      <div className={`sidebar__backdrop${open ? ' sidebar__backdrop--show' : ''}`} onClick={onClose} aria-hidden="true" />
      <aside className={`sidebar${open ? ' sidebar--open' : ''}`} aria-label="Боковая панель">
      <div className="sidebar__header">
        <span className="sidebar__logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="28" height="28" fill="none"
               stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2.5" y="4.5" width="19" height="15" rx="2.5" />
            <path d="M6.5 10l2.5 2-2.5 2" />
            <line x1="11.5" y1="14" x2="16" y2="14" className="sidebar__logo-cursor" />
          </svg>
        </span>
        <span className="sidebar__title">UniBot</span>
        <button type="button" className="sidebar__close" aria-label="Закрыть меню" onClick={onClose}>✕</button>
      </div>

      <button className="sidebar__new-chat" onClick={onNewChat}>
        <span className="sidebar__prompt">$</span> Новый чат
      </button>

      <ul className="sidebar__chats">
        {dialogs.length === 0 && (
          <li className="sidebar__chat sidebar__chat--placeholder">// диалогов пока нет</li>
        )}
        {dialogs.map((d) => (
          <li
            key={d.dialog_id}
            className={`sidebar__chat${d.dialog_id === activeId ? ' sidebar__chat--active' : ''}`}
          >
            <button type="button" className="sidebar__chat-open" onClick={() => onSelect(d.dialog_id)}>
              {d.title || 'Новый чат'}
            </button>
            <button
              type="button"
              className="sidebar__chat-del"
              title="Удалить диалог"
              onClick={() => onDelete(d.dialog_id)}
            >
              ✕
            </button>
          </li>
        ))}
      </ul>

      <div className="sidebar__footer">
        {user && (
          <div className="sidebar__user" title={user.email || ''}>
            {user.picture && <img className="sidebar__avatar" src={user.picture} alt="" />}
            <span className="sidebar__user-name">{user.name || user.email}</span>
          </div>
        )}
        <button type="button" className="sidebar__auth sidebar__auth--ghost" onClick={onLogout}>
          Выйти
        </button>
      </div>
      </aside>
    </>
  );
}
