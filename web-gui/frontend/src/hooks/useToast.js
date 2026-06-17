import { useCallback, useRef, useState } from 'react';

/** Single auto-dismissing toast notification. */
export function useToast() {
  const [toast, setToast] = useState(null);
  const timer = useRef(null);

  const show = useCallback((message, variant = 'info', durationMs = 4000) => {
    if (timer.current) clearTimeout(timer.current);
    setToast({ message, variant });
    timer.current = setTimeout(() => setToast(null), durationMs);
  }, []);

  return { toast, show };
}
