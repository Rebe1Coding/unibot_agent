/** Renders the assistant answer's source list. */
export default function Sources({ sources }) {
  return (
    <div className="sources">
      <div className="sources__title">Источники</div>
      {sources.map((s, i) => (
        <div className="source-item" key={i}>
          <div className="source-item__title">
            {s.url ? (
              <a href={s.url} target="_blank" rel="noopener noreferrer">{s.title || s.url}</a>
            ) : (
              s.title || ''
            )}
          </div>
          {s.snippet && <div className="source-item__snippet">{s.snippet}</div>}
        </div>
      ))}
    </div>
  );
}
