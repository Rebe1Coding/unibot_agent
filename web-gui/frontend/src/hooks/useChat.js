import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, TimeoutError } from '../api/client.js';
import { delay, isValidMessage } from '../lib/utils.js';
import { getAudioDuration } from '../lib/audioDuration.js';

const CLARIFICATION_LIMIT = 5;
// Аудио длиннее этого — вероятно лекция, спрашиваем пользователя; короче — обращение к агенту.
const LECTURE_THRESHOLD_SEC = 120;

/** Owns the active dialog's messages: streamed send/voice/clarification flows and errors. */
export function useChat({ api, dialogId, onTurnSaved, toast, setBanner, inputRef }) {
  const [messages, setMessages] = useState([]);
  const [typing, setTyping] = useState(false);
  const [inputEnabled, setInputEnabled] = useState(false);

  const idRef = useRef(0);
  const submittingRef = useRef(false);
  const clarificationDepthRef = useRef(0);
  const lectureTaskRef = useRef(null);          // task_id текущей расшифровки лекции
  const pendingVoiceFiles = useRef(new Map());  // id сообщения-вопроса → аудиофайл

  const nextId = () => { idRef.current += 1; return idRef.current; };

  const focusInput = useCallback(() => {
    if (inputRef && inputRef.current) inputRef.current.focus();
  }, [inputRef]);

  const addUserMessage = useCallback((text, attachments = []) => {
    setMessages((prev) => [...prev, { id: nextId(), role: 'user', text, attachments }]);
  }, []);

  const addSystemMessage = useCallback((text, variant = 'info') => {
    setMessages((prev) => [...prev, { id: nextId(), role: 'system', text, variant }]);
  }, []);

  const addAssistantFiles = useCallback((answer, files) => {
    setMessages((prev) => [...prev, {
      id: nextId(), role: 'assistant', answer,
      thoughts: [], steps: [], sources: [], files,
      clarification: null, answered: null, streaming: false, phase: 'done',
    }]);
  }, []);

  const handleError = useCallback(async (err) => {
    if (err instanceof TimeoutError) {
      toast('Сервер не ответил вовремя. Попробуйте ещё раз.', 'error');
      return;
    }
    if (err instanceof ApiError) {
      switch (err.status) {
        case 401:
          // Сессия истекла — возвращаем на экран входа.
          setBanner({ text: 'Сессия истекла. Войдите снова.', variant: 'error' });
          await delay(1200);
          window.location.reload();
          return;
        case 422:
          toast('Ошибка в данных запроса. Проверьте ввод.', 'error');
          return;
        case 429:
          toast('Слишком много запросов. Подождите немного.', 'warning');
          setInputEnabled(false);
          await delay(2000);
          setInputEnabled(true);
          return;
        case 500:
        case 502:
        case 503:
        case 504:
          toast('Произошла ошибка на сервере. Попробуйте позже.', 'error');
          return;
        default:
          toast(`Ошибка ${err.status}`, 'error');
          return;
      }
    }
    toast('Сервер временно недоступен. Попробуйте позже.', 'error');
  }, [toast, setBanner]);

  /** Apply one streamed event to the in-progress assistant message. */
  const applyEvent = useCallback((event, patch) => {
    switch (event.type) {
      case 'thinking':
        patch((m) => ({
          ...m,
          phase: m.phase === 'answering' ? m.phase : 'thinking',
          thoughts: [...m.thoughts, event.text],
        }));
        break;
      case 'tool_start':
        patch((m) => ({
          ...m,
          phase: 'tools',
          steps: [...m.steps, {
            tool: event.tool,
            label: event.label,
            query: event.query,
            status: 'running',
            found: true,
            sources: [],
            files: [],
          }],
        }));
        break;
      case 'tool_end':
        patch((m) => {
          const steps = m.steps.slice();
          for (let i = steps.length - 1; i >= 0; i -= 1) {
            if (steps[i].tool === event.tool && steps[i].status === 'running') {
              steps[i] = {
                ...steps[i],
                status: 'done',
                found: event.found,
                sources: event.sources || [],
                files: event.files || [],
              };
              break;
            }
          }
          return { ...m, steps };
        });
        break;
      case 'token':
        patch((m) => ({ ...m, phase: 'answering', answer: m.answer + event.text }));
        break;
      case 'done':
        if (!event.clarification) clarificationDepthRef.current = 0;
        patch((m) => ({
          ...m,
          answer: event.clarification ? '' : (event.answer || m.answer),
          sources: event.sources || [],
          files: event.files || [],
          clarification: event.clarification || null,
          streaming: false,
          phase: 'done',
        }));
        break;
      case 'error':
        patch((m) => ({ ...m, streaming: false, phase: 'done' }));
        toast(event.message || 'Произошла ошибка на сервере.', 'error');
        break;
      default:
        break;
    }
  }, [toast]);

  const sendText = useCallback(async (message, clarificationResponse = null, opts = {}) => {
    if (submittingRef.current || !dialogId) return;
    submittingRef.current = true;
    setInputEnabled(false);
    setTyping(false);

    if (!opts.skipUserBubble) {
      addUserMessage(opts.messageOverride || message, opts.attachmentsForBubble || []);
    }

    const assistantId = nextId();
    setMessages((prev) => [...prev, {
      id: assistantId,
      role: 'assistant',
      answer: '',
      thoughts: [],
      steps: [],
      sources: [],
      files: [],
      clarification: null,
      answered: null,
      streaming: true,
      phase: 'thinking',
    }]);
    const patch = (update) => setMessages((prev) => prev.map((m) => (
      m.id === assistantId ? (typeof update === 'function' ? update(m) : { ...m, ...update }) : m
    )));

    try {
      const payload = opts.messageOverride || message;
      await api.chatStream({
        dialogId,
        message: payload,
        clarificationResponse,
        onEvent: (event) => applyEvent(event, patch),
      });
      patch((m) => (m.streaming ? { ...m, streaming: false, phase: 'done' } : m));
      if (onTurnSaved) onTurnSaved();
    } catch (err) {
      setMessages((prev) => prev.filter((m) => !(
        m.id === assistantId && !m.answer && m.steps.length === 0
      )));
      patch((m) => ({ ...m, streaming: false, phase: 'done' }));
      await handleError(err);
    } finally {
      submittingRef.current = false;
      setInputEnabled(true);
      focusInput();
    }
  }, [api, dialogId, onTurnSaved, addUserMessage, applyEvent, handleError, focusInput]);

  // Опрашивает статус задачи распознавания до завершения или таймаута.
  const pollVoice = useCallback(async (taskId, tries = 60) => {
    for (let i = 0; i < tries; i += 1) {
      await delay(2000);
      const res = await api.voiceStatus(taskId).catch(() => null);
      if (res && res.status !== 'processing') return res;
    }
    return { status: 'error', error: 'timeout' };
  }, [api]);

  // Короткое голосовое: распознаём и сразу передаём текст агенту.
  const runCommandVoice = useCallback(async (file) => {
    addUserMessage('🎙 Голосовое сообщение', [{ name: file.name }]);
    addSystemMessage('🎧 Агент вас слушает…');
    setInputEnabled(false);
    try {
      const { task_id: taskId } = await api.voice({ file, mode: 'command' });
      const res = await pollVoice(taskId);
      const text = (res.text || '').trim();
      if (res.status === 'completed' && text) {
        await sendText(text, null, { skipUserBubble: true, messageOverride: text });
      } else {
        addSystemMessage('Не удалось распознать речь. Попробуйте ещё раз.', 'error');
      }
    } catch (err) {
      await handleError(err);
    } finally {
      setInputEnabled(true);
    }
  }, [api, addUserMessage, addSystemMessage, pollVoice, sendText, handleError]);

  // Длинное аудио как лекция: запускаем расшифровку в фоне, статус — командой /status.
  const runLectureVoice = useCallback(async (file) => {
    addUserMessage('🎙 Голосовое (лекция)', [{ name: file.name }]);
    try {
      const { task_id: taskId } = await api.voice({ file, mode: 'lecture' });
      lectureTaskRef.current = taskId;
      addSystemMessage('📝 Распознаю лекцию — это займёт время. Проверьте статус командой /status.');
    } catch (err) {
      await handleError(err);
    }
  }, [api, addUserMessage, addSystemMessage, handleError]);

  // Проверка статуса фоновой расшифровки лекции (команда /status).
  const checkLectureStatus = useCallback(async () => {
    const taskId = lectureTaskRef.current;
    if (!taskId) {
      addSystemMessage('Нет активных расшифровок лекций.');
      return;
    }
    let res;
    try {
      res = await api.voiceStatus(taskId);
    } catch (err) {
      await handleError(err);
      return;
    }
    if (res.status === 'processing') {
      addSystemMessage('⏳ Лекция ещё распознаётся. Загляните позже — /status.');
      return;
    }
    lectureTaskRef.current = null;
    if (res.status === 'completed') {
      addAssistantFiles('✅ Конспект лекции готов.', res.download_url ? [res.download_url] : []);
    } else {
      addSystemMessage(`Ошибка распознавания лекции: ${res.error || 'неизвестно'}`, 'error');
    }
  }, [api, addSystemMessage, addAssistantFiles, handleError]);

  // Длинное аудио — спрашиваем, что с ним делать.
  const promptVoiceChoice = useCallback((file) => {
    const id = nextId();
    pendingVoiceFiles.current.set(id, file);
    setMessages((prev) => [...prev, {
      id, role: 'voicechoice', answered: null,
      text: 'Аудио длиннее 2 минут. Что с ним сделать?',
      options: [
        { label: 'Конспект лекции', mode: 'lecture' },
        { label: 'Обработать как обращение', mode: 'command' },
      ],
    }]);
  }, []);

  const handleVoiceChoice = useCallback((messageId, option) => {
    const file = pendingVoiceFiles.current.get(messageId);
    pendingVoiceFiles.current.delete(messageId);
    setMessages((prev) => prev.map((m) => (
      m.id === messageId ? { ...m, answered: option.label } : m
    )));
    if (!file) return;
    if (option.mode === 'lecture') runLectureVoice(file);
    else runCommandVoice(file);
  }, [runLectureVoice, runCommandVoice]);

  const sendVoiceFile = useCallback(async (file, durationSec = null) => {
    let dur = durationSec;
    if (dur == null) dur = await getAudioDuration(file);
    if (dur != null && dur >= LECTURE_THRESHOLD_SEC) {
      promptVoiceChoice(file);
    } else {
      await runCommandVoice(file);
    }
  }, [promptVoiceChoice, runCommandVoice]);

  const sendMessage = useCallback(async (text, files = []) => {
    if (submittingRef.current) return;
    const trimmed = (text || '').trim();
    if (!trimmed && files.length === 0) return;
    if (trimmed && !isValidMessage(trimmed)) {
      toast('Сообщение должно быть от 1 до 4096 символов.', 'warning');
      return;
    }
    const attachmentsForBubble = files.map((f) => ({ name: f.name }));
    const fileNotes = files.length
      ? `\n\n[Прикреплённые файлы: ${files.map((f) => f.name).join(', ')}]`
      : '';
    clarificationDepthRef.current = 0;
    await sendText(trimmed || '(только вложения)', null, {
      attachmentsForBubble,
      messageOverride: (trimmed || 'Прикрепил(а) файлы') + fileNotes,
    });
  }, [sendText, toast]);

  const handleClarification = useCallback((messageId, option) => {
    setMessages((prev) => prev.map((m) => (m.id === messageId ? { ...m, answered: option.label } : m)));
    if (clarificationDepthRef.current >= CLARIFICATION_LIMIT) {
      toast('Слишком много уточнений подряд. Уточните вопрос самостоятельно.', 'warning');
      clarificationDepthRef.current = 0;
      return;
    }
    clarificationDepthRef.current += 1;
    sendText(option.value, option.value);
  }, [sendText, toast]);

  // Загружаем сообщения активного диалога при его смене (new_chat / переключение).
  useEffect(() => {
    if (!dialogId) return;
    let active = true;
    setInputEnabled(false);
    setTyping(false);
    clarificationDepthRef.current = 0;
    (async () => {
      try {
        const data = await api.dialogHistory(dialogId);
        const list = (data && data.messages) || [];
        if (!active) return;
        setMessages(list.map((m) => (
          m.role === 'user'
            ? { id: nextId(), role: 'user', text: m.content, attachments: [] }
            : {
                id: nextId(),
                role: 'assistant',
                answer: m.content,
                thoughts: [],
                steps: [],
                sources: [],
                files: [],
                clarification: null,
                answered: null,
                streaming: false,
                phase: 'done',
              }
        )));
      } catch {
        if (active) toast('Не удалось загрузить диалог.', 'warning');
      } finally {
        if (active) {
          setInputEnabled(true);
          focusInput();
        }
      }
    })();
    return () => { active = false; };
  }, [api, dialogId, toast, focusInput]);

  return {
    messages,
    typing,
    inputEnabled,
    sendMessage,
    sendVoiceFile,
    handleClarification,
    handleVoiceChoice,
    checkLectureStatus,
  };
}
