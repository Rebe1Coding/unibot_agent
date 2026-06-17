import { useEffect } from 'react';

/** Poll /health every 60s and push a banner descriptor (or null) to setBanner. */
export function useHealth(api, setBanner) {
  useEffect(() => {
    let active = true;

    const check = async () => {
      try {
        const data = await api.health();
        if (!active) return;
        if (data && data.status === 'degraded') {
          const broken = Object.entries(data.services || {})
            .filter(([, v]) => v && v.status !== 'ok')
            .map(([k, v]) => `${k}: ${v.status}`)
            .join(', ');
          setBanner({
            text: broken
              ? `Часть функций может быть недоступна (${broken})`
              : 'Часть функций может быть недоступна',
            variant: 'warning',
          });
        } else {
          setBanner(null);
        }
      } catch {
        if (active) setBanner({ text: 'Не удалось проверить статус сервисов.', variant: 'error' });
      }
    };

    check();
    const id = setInterval(check, 60_000);
    return () => { active = false; clearInterval(id); };
  }, [api, setBanner]);
}
