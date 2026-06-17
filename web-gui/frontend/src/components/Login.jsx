/** Full-screen login gate shown until the user signs in with Google. */
export default function Login({ onLogin }) {
  return (
    <div className="login">
      <div className="login__card">
        <span className="login__logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="40" height="40" fill="none"
               stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
            <rect x="2.5" y="4.5" width="19" height="15" rx="2.5" />
            <path d="M6.5 10l2.5 2-2.5 2" />
            <line x1="11.5" y1="14" x2="16" y2="14" />
          </svg>
        </span>
        <h1 className="login__title">UniBot</h1>
        <p className="login__subtitle">Войдите, чтобы открыть чат с ассистентом.</p>
        <button type="button" className="login__google" onClick={onLogin}>
          <svg width="18" height="18" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#EA4335" d="M24 9.5c3.5 0 6.6 1.2 9 3.6l6.7-6.7C35.6 2.4 30.1 0 24 0 14.6 0 6.4 5.4 2.6 13.2l7.8 6.1C12.2 13.2 17.6 9.5 24 9.5z"/>
            <path fill="#4285F4" d="M46.1 24.5c0-1.6-.1-3.1-.4-4.5H24v9h12.4c-.5 2.9-2.1 5.3-4.6 7l7.1 5.5c4.2-3.9 6.6-9.6 6.6-16.5z"/>
            <path fill="#FBBC05" d="M10.4 28.7c-.5-1.4-.8-2.9-.8-4.5s.3-3.1.8-4.5l-7.8-6.1C1 16.8 0 20.3 0 24s1 7.2 2.6 10.4l7.8-5.7z"/>
            <path fill="#34A853" d="M24 48c6.1 0 11.3-2 15-5.5l-7.1-5.5c-2 1.4-4.6 2.2-7.9 2.2-6.4 0-11.8-3.7-13.6-9.1l-7.8 5.7C6.4 42.6 14.6 48 24 48z"/>
          </svg>
          Войти через Google
        </button>
      </div>
    </div>
  );
}
