/** Internal reasoning the agent shared before its final answer. */
export default function AgentThoughts({ thoughts }) {
  return (
    <div className="agent-thoughts">
      <div className="agent-thoughts__title">Размышления</div>
      {thoughts.map((text, i) => (
        <div className="agent-thoughts__item" key={i}>{text}</div>
      ))}
    </div>
  );
}
