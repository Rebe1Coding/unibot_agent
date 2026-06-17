/** One tool invocation in the agent timeline: label, query, status and result count. */
function ToolStep({ step }) {
  const { label, query, status, found, sources = [], files = [] } = step;
  const running = status === 'running';
  const count = sources.length + files.length;

  let meta = '';
  if (!running) {
    if (found === false) meta = 'ничего не найдено';
    else if (count > 0) meta = `найдено результатов: ${count}`;
    else meta = 'готово';
  }

  return (
    <div className={`tool-step tool-step--${status}`}>
      <span className="tool-step__icon" aria-hidden="true">
        {running ? <span className="cursor cursor--solid" /> : (found === false ? '∅' : '✓')}
      </span>
      <div className="tool-step__body">
        <div className="tool-step__label">
          {label}
          {query && <span className="tool-step__query"> · {query}</span>}
        </div>
        {meta && <div className="tool-step__meta">{meta}</div>}
      </div>
    </div>
  );
}

/** The "Поиск/Инструмент" phase: a list of tools the agent used. */
export default function AgentSteps({ steps }) {
  return (
    <div className="agent-steps">
      <div className="agent-steps__title">Действия агента</div>
      {steps.map((step, i) => <ToolStep key={i} step={step} />)}
    </div>
  );
}
