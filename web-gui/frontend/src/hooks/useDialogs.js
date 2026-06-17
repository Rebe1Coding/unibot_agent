import { useCallback, useEffect, useRef, useState } from 'react';

/** Owns the dialog list and the active dialog; handles new_chat and switching. */
export function useDialogs({ api, enabled, toast }) {
  const [dialogs, setDialogs] = useState([]);
  const [activeId, setActiveId] = useState(null);
  const [loading, setLoading] = useState(true);
  const initedRef = useRef(false);

  const refresh = useCallback(async () => {
    const data = await api.listDialogs();
    const list = (data && data.dialogs) || [];
    setDialogs(list);
    return list;
  }, [api]);

  // Первичная загрузка: берём последний диалог или создаём новый.
  useEffect(() => {
    if (!enabled || initedRef.current) return;
    initedRef.current = true;
    (async () => {
      try {
        const list = await refresh();
        if (list.length > 0) {
          setActiveId(list[0].dialog_id);
        } else {
          const created = await api.newDialog(null);
          setDialogs([{ dialog_id: created.dialog_id, title: created.title }]);
          setActiveId(created.dialog_id);
        }
      } catch {
        toast('Не удалось загрузить диалоги.', 'error');
      } finally {
        setLoading(false);
      }
    })();
  }, [enabled, refresh, api, toast]);

  // new_chat: новый диалог, старому в Redis выставится TTL 1 час на бэкенде.
  const newChat = useCallback(async () => {
    try {
      const created = await api.newDialog(activeId);
      setDialogs((prev) => [{ dialog_id: created.dialog_id, title: created.title }, ...prev]);
      setActiveId(created.dialog_id);
    } catch {
      toast('Не удалось создать новый чат.', 'error');
    }
  }, [api, activeId, toast]);

  const selectDialog = useCallback((id) => {
    if (id !== activeId) setActiveId(id);
  }, [activeId]);

  const removeDialog = useCallback(async (id) => {
    try {
      await api.deleteDialog(id);
    } catch {
      toast('Не удалось удалить диалог.', 'error');
      return;
    }
    const list = await refresh();
    if (id === activeId) {
      if (list.length > 0) setActiveId(list[0].dialog_id);
      else {
        const created = await api.newDialog(null);
        setDialogs([{ dialog_id: created.dialog_id, title: created.title }]);
        setActiveId(created.dialog_id);
      }
    }
  }, [api, activeId, refresh, toast]);

  return { dialogs, activeId, loading, refresh, newChat, selectDialog, removeDialog };
}
