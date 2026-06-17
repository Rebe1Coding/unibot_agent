import { useCallback, useEffect, useState } from 'react';

/** Loads the current user from /auth/me and exposes login/logout. */
export function useAuth(api) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    (async () => {
      try {
        const me = await api.me();
        if (active) setUser(me);
      } catch {
        if (active) setUser(null);
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => { active = false; };
  }, [api]);

  const login = useCallback(() => { window.location.href = '/auth/login'; }, []);

  const logout = useCallback(async () => {
    try { await api.logout(); } catch { /* игнорируем — всё равно перезагружаем */ }
    setUser(null);
    window.location.reload();
  }, [api]);

  return { user, loading, authenticated: !!user, login, logout };
}
