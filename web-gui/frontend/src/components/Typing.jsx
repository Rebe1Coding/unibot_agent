/** Blinking terminal cursor shown while the agent is processing. */
export default function Typing() {
  return (
    <div className="typing" aria-hidden="true">
      <span className="typing__prompt">unibot ›</span>
      <span className="cursor cursor--solid" />
    </div>
  );
}
