import { useEffect, useRef } from 'react';
import Message from './Message.jsx';
import Welcome from './Welcome.jsx';
import Typing from './Typing.jsx';

/** Scrollable message log; auto-scrolls to bottom on new content. */
export default function MessageList({ messages, typing, onClarification, onVoiceChoice }) {
  const endRef = useRef(null);

  useEffect(() => {
    if (endRef.current) endRef.current.scrollIntoView({ block: 'end' });
  }, [messages, typing]);

  return (
    <section className="chat__messages" aria-live="polite">
      {messages.length === 0 && <Welcome />}
      {messages.map((m, i) => (
        <Message
          key={m.id}
          message={m}
          isLast={i === messages.length - 1}
          onClarification={onClarification}
          onVoiceChoice={onVoiceChoice}
        />
      ))}
      {typing && <Typing />}
      <div ref={endRef} />
    </section>
  );
}
