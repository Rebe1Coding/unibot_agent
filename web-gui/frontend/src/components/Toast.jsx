/** Transient notification pinned to the bottom-right. */
export default function Toast({ toast }) {
  if (!toast) return null;
  return (
    <div className={`toast toast--${toast.variant}`} role="alert">
      {toast.message}
    </div>
  );
}
