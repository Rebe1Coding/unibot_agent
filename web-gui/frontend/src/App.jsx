import { useCallback, useMemo, useRef, useState } from 'react';
import { ApiClient } from './api/client.js';
import { VoiceRecorder } from './lib/voiceRecorder.js';
import { isAudio, validateFiles } from './lib/uploader.js';
import { useToast } from './hooks/useToast.js';
import { useHealth } from './hooks/useHealth.js';
import { useAuth } from './hooks/useAuth.js';
import { useDialogs } from './hooks/useDialogs.js';
import { useChat } from './hooks/useChat.js';
import Sidebar from './components/Sidebar.jsx';
import Header from './components/Header.jsx';
import MessageList from './components/MessageList.jsx';
import Composer from './components/Composer.jsx';
import Login from './components/Login.jsx';
import Toast from './components/Toast.jsx';

export default function App() {
  const api = useMemo(() => new ApiClient({ timeoutMs: 120_000 }), []);
  const { toast, show } = useToast();
  const [banner, setBanner] = useState(null);
  const inputRef = useRef(null);
  const recorderRef = useRef(null);
  if (recorderRef.current == null) recorderRef.current = new VoiceRecorder();

  const [attachments, setAttachments] = useState([]);
  const [recording, setRecording] = useState(false);

  const { user, loading: authLoading, authenticated, login, logout } = useAuth(api);
  useHealth(api, setBanner);

  const {
    dialogs, activeId, loading: dialogsLoading, refresh: refreshDialogs,
    newChat, selectDialog, removeDialog,
  } = useDialogs({ api, enabled: authenticated, toast: show });

  const {
    messages, typing, inputEnabled, sendMessage, sendVoiceFile,
    handleClarification, handleVoiceChoice, checkLectureStatus,
  } = useChat({ api, dialogId: activeId, onTurnSaved: refreshDialogs, toast: show, setBanner, inputRef });

  const onCommand = useCallback((name) => {
    if (name === '/new') newChat();
    else if (name === '/status') checkLectureStatus();
  }, [newChat, checkLectureStatus]);

  const handleFiles = useCallback((fileList) => {
    const audio = [];
    const others = [];
    for (const f of fileList) (isAudio(f) ? audio : others).push(f);
    if (others.length) {
      const { accepted, rejected } = validateFiles(others);
      if (accepted.length) setAttachments((prev) => [...prev, ...accepted]);
      rejected.forEach((r) => show(r.reason, 'warning'));
    }
    audio.forEach((f) => sendVoiceFile(f));
  }, [sendVoiceFile, show]);

  const onSend = useCallback((text, files) => {
    sendMessage(text, files);
    setAttachments([]);
  }, [sendMessage]);

  const removeAttachment = useCallback((idx) => {
    setAttachments((prev) => prev.filter((_, i) => i !== idx));
  }, []);

  const toggleVoice = useCallback(async () => {
    const recorder = recorderRef.current;
    if (recorder.isRecording) {
      try {
        const blob = await recorder.stop();
        const durationSec = recorder.durationSec;
        setRecording(false);
        if (blob && blob.size > 0) {
          const ext = blob.type.includes('ogg') ? 'ogg' : blob.type.includes('mp4') ? 'm4a' : 'webm';
          const file = new File([blob], `voice-${Date.now()}.${ext}`, { type: blob.type });
          await sendVoiceFile(file, durationSec);
        }
      } catch (err) {
        setRecording(false);
        show(`Ошибка записи: ${err.message}`, 'error');
      }
      return;
    }
    try {
      await recorder.start();
      setRecording(true);
    } catch (err) {
      show(`Не удалось начать запись: ${err.message}`, 'error');
    }
  }, [sendVoiceFile, show]);

  if (authLoading) {
    return <div className="app-loading">Загрузка…</div>;
  }
  if (!authenticated) {
    return (
      <>
        <Login onLogin={login} />
        <Toast toast={toast} />
      </>
    );
  }

  return (
    <div className="app">
      <Sidebar
        dialogs={dialogs}
        activeId={activeId}
        onNewChat={newChat}
        onSelect={selectDialog}
        onDelete={removeDialog}
        user={user}
        onLogout={logout}
      />
      <main className="chat">
        <Header banner={banner} />
        <MessageList
          messages={messages}
          typing={typing}
          onClarification={handleClarification}
          onVoiceChoice={handleVoiceChoice}
        />
        <Composer
          inputRef={inputRef}
          enabled={inputEnabled && !dialogsLoading}
          recording={recording}
          attachments={attachments}
          onSend={onSend}
          onCommand={onCommand}
          onFiles={handleFiles}
          onRemoveAttachment={removeAttachment}
          onToggleVoice={toggleVoice}
        />
      </main>
      <Toast toast={toast} />
    </div>
  );
}
