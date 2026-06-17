import { useEffect, useRef } from 'react';
import { renderMarkdown, highlightCodeBlocks } from '../lib/markdown.js';
import { attachCopyButtons } from '../lib/codeCopy.js';
import Sources from './Sources.jsx';
import Files from './Files.jsx';
import Clarification from './Clarification.jsx';
import AgentSteps from './AgentSteps.jsx';
import AgentThoughts from './AgentThoughts.jsx';

function UserMessage({ text, attachments }) {
  return (
    <div className="message message--user">
      <div className="message__prompt" aria-hidden="true">студент@unibot:~$</div>
      <div className="message__bubble">{text}</div>
      {attachments && attachments.length > 0 && (
        <div className="message__attachments">
          {attachments.map((a, i) => (
            <span className="attachment-chip" key={i}>{a.name}</span>
          ))}
        </div>
      )}
    </div>
  );
}

function SystemMessage({ text, variant }) {
  return (
    <div className="message message--system">
      <div className={`message__bubble${variant === 'error' ? ' message__bubble--error' : ''}`}>
        <em>{text}</em>
      </div>
    </div>
  );
}

function AssistantMessage({ message, isLast, onClarification }) {
  const {
    clarification, answer, sources, files, answered,
    thoughts = [], steps = [], streaming, phase,
  } = message;
  const text = clarification ? clarification.question : answer;
  const hasOptions = clarification && clarification.options && clarification.options.length > 0;
  const thinking = streaming && phase === 'thinking';
  const answering = streaming && phase === 'answering';
  const showBubble = Boolean(text) || answering;

  // Подсвечиваем код и добавляем кнопку копирования после каждого обновления текста.
  const bodyRef = useRef(null);
  useEffect(() => {
    highlightCodeBlocks(bodyRef.current);
    attachCopyButtons(bodyRef.current);
  }, [text]);

  return (
    <div className="message message--assistant">
      <div className="message__prompt" aria-hidden="true">unibot ›</div>
      {thoughts.length > 0 && <AgentThoughts thoughts={thoughts} />}
      {steps.length > 0 && <AgentSteps steps={steps} />}
      {thinking && thoughts.length === 0 && (
        <div className="phase-status">
          <span className="cursor cursor--solid" />
          <span className="phase-status__label">Анализирую запрос…</span>
        </div>
      )}
      {showBubble && (
        <div className="message__bubble message__bubble--md">
          <span ref={bodyRef} dangerouslySetInnerHTML={{ __html: renderMarkdown(text) }} />
          {answering && <span className="cursor" />}
        </div>
      )}
      {sources && sources.length > 0 && <Sources sources={sources} />}
      {files && files.length > 0 && <Files files={files} />}
      {hasOptions && (
        <Clarification
          options={clarification.options}
          interactive={isLast && !answered}
          answered={answered}
          onPick={(opt) => onClarification(message.id, opt)}
        />
      )}
    </div>
  );
}

function VoiceChoiceMessage({ message, isLast, onVoiceChoice }) {
  return (
    <div className="message message--assistant">
      <div className="message__prompt" aria-hidden="true">unibot ›</div>
      <div className="message__bubble"><em>{message.text}</em></div>
      <Clarification
        options={message.options}
        interactive={isLast && !message.answered}
        answered={message.answered}
        onPick={(opt) => onVoiceChoice(message.id, opt)}
      />
    </div>
  );
}

/** Dispatches to the right bubble by message role. */
export default function Message({ message, isLast, onClarification, onVoiceChoice }) {
  if (message.role === 'user') {
    return <UserMessage text={message.text} attachments={message.attachments} />;
  }
  if (message.role === 'system') {
    return <SystemMessage text={message.text} variant={message.variant} />;
  }
  if (message.role === 'voicechoice') {
    return <VoiceChoiceMessage message={message} isLast={isLast} onVoiceChoice={onVoiceChoice} />;
  }
  return <AssistantMessage message={message} isLast={isLast} onClarification={onClarification} />;
}
