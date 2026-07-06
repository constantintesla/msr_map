import { useCallback, useEffect, useRef, useState } from 'react';
import {
  fetchChatMediaBlob,
  fetchChatMessages,
  fetchChatRecipients,
  sendChatMessage,
  type ChatMessage,
  type ChatThread,
} from '../api/client';
import { commanderSocketHub, engineerSocketHub } from '../ws/hubs';

type ChatMode = 'admin' | 'commander' | 'engineer';

interface ChatPanelProps {
  mode: ChatMode;
  side: 'A' | 'B';
  thread?: ChatThread;
  onSideChange?: (side: 'A' | 'B') => void;
  onThreadChange?: (thread: ChatThread) => void;
  className?: string;
  refreshToken?: number;
}

function activeThread(mode: ChatMode, thread?: ChatThread): ChatThread {
  if (mode === 'engineer') return 'eng';
  if (mode === 'commander') return thread ?? 'cmd';
  return thread ?? 'cmd';
}

function isMineMessage(msg: ChatMessage, mode: ChatMode, username: string): boolean {
  if (mode === 'admin') return msg.sender_role === 'admin';
  if (mode === 'commander') return msg.sender_role === 'commander';
  if (msg.sender_role === 'admin') return false;
  return msg.sender_name === username || msg.sender_role === 'engineer';
}

function ChatMedia({ messageId, mediaType }: { messageId: number; mediaType: string }) {
  const [url, setUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    fetchChatMediaBlob(messageId)
      .then((blob) => {
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setUrl(objectUrl);
      })
      .catch(() => {
        if (!cancelled) setError(true);
      });
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [messageId]);

  if (error) return <p className="text-xs text-sideB mt-1">Не удалось загрузить медиа</p>;
  if (!url) return <p className="text-xs text-zinc-500 mt-1">Загрузка…</p>;
  if (mediaType === 'video') {
    return <video src={url} controls playsInline className="mt-2 max-w-full rounded-lg max-h-48 bg-black" />;
  }
  return <img src={url} alt="" className="mt-2 max-w-full rounded-lg max-h-48 object-contain bg-black/30" />;
}

function MessageBubble({
  msg,
  mine,
  mySide,
  canReply,
  onReply,
}: {
  msg: ChatMessage;
  mine: boolean;
  mySide: 'A' | 'B';
  canReply?: boolean;
  onReply?: () => void;
}) {
  const mineCls = mySide === 'A' ? 'bg-sideA/25 border-sideA/40' : 'bg-sideB/25 border-sideB/40';
  return (
    <div className={`flex flex-col ${mine ? 'items-end' : 'items-start'}`}>
      <div
        className={`max-w-[92%] rounded-2xl px-3 py-2 text-sm border ${
          mine ? `${mineCls} text-zinc-100` : 'bg-zinc-800 border-zinc-700 text-zinc-200'
        }`}
      >
        <div className="text-[10px] text-zinc-500 mb-0.5">
          {msg.sender_name}
          {msg.recipient_username && (
            <>
              <span className="mx-1">→</span>
              <span className="text-warning">{msg.recipient_username}</span>
            </>
          )}
          <span className="mx-1">·</span>
          {new Date(msg.created_at).toLocaleTimeString()}
        </div>
        {msg.text && <p className="whitespace-pre-wrap break-words leading-snug">{msg.text}</p>}
        {msg.has_media && msg.media_type && <ChatMedia messageId={msg.id} mediaType={msg.media_type} />}
      </div>
      {canReply && onReply && msg.sender_role === 'engineer' && (
        <button
          type="button"
          className="mt-1 text-[10px] text-sideA hover:text-sideA/80 px-1"
          onClick={onReply}
        >
          Ответить
        </button>
      )}
    </div>
  );
}

export default function ChatPanel({
  mode,
  side,
  thread: threadProp,
  onSideChange,
  onThreadChange,
  className = '',
  refreshToken = 0,
}: ChatPanelProps) {
  const [commanderThread, setCommanderThread] = useState<ChatThread>('cmd');
  const thread =
    mode === 'commander' ? commanderThread : activeThread(mode, threadProp);
  const canDirectReply = (mode === 'admin' || mode === 'commander') && thread === 'eng';
  const showComposer = mode === 'engineer' || thread === 'cmd' || canDirectReply;
  const username = localStorage.getItem('username') || '';
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [recipients, setRecipients] = useState<Array<{ username: string }>>([]);
  const [replyTo, setReplyTo] = useState<string | null>(null);
  const [recipient, setRecipient] = useState<string>('');
  useEffect(() => {
    if (!canDirectReply) {
      setRecipients([]);
      setReplyTo(null);
      setRecipient('');
      return;
    }
    fetchChatRecipients(mode === 'admin' ? side : undefined)
      .then(setRecipients)
      .catch(() => setRecipients([]));
  }, [canDirectReply, mode, side]);

  useEffect(() => {
    setReplyTo(null);
    setRecipient('');
  }, [thread, side]);

  useEffect(() => {
    if (replyTo) setRecipient(replyTo);
  }, [replyTo]);
  const [text, setText] = useState('');
  const [file, setFile] = useState<File | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const listRef = useRef<HTMLDivElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const lastIdRef = useRef(0);

  const load = useCallback(
    (incremental = false) => {
      const afterId = incremental ? lastIdRef.current : 0;
      const sideArg = mode === 'admin' ? side : undefined;
      return fetchChatMessages(sideArg, afterId, thread).then((res) => {
        if (incremental && afterId > 0) {
          if (res.items.length > 0) {
            setMessages((prev) => {
              const ids = new Set(prev.map((m) => m.id));
              const merged = [...prev, ...res.items.filter((m) => !ids.has(m.id))];
              lastIdRef.current = merged[merged.length - 1]?.id ?? lastIdRef.current;
              return merged;
            });
          }
        } else {
          setMessages(res.items);
          lastIdRef.current = res.items[res.items.length - 1]?.id ?? 0;
        }
        setError('');
      });
    },
    [mode, side, thread]
  );

  useEffect(() => {
    lastIdRef.current = 0;
    void load(false);
  }, [load, side, thread]);

  useEffect(() => {
    if (refreshToken > 0) void load(true);
  }, [refreshToken, load]);

  useEffect(() => {
    const poll = setInterval(() => void load(true), 5000);
    return () => clearInterval(poll);
  }, [load]);

  useEffect(() => {
    if (mode !== 'commander' && mode !== 'engineer') return;
    const hub = mode === 'commander' ? commanderSocketHub : engineerSocketHub;

    return hub.subscribe((packet) => {
      if (packet.e !== 'chat' || packet.t !== side) return;
      const pThread = (packet.thread as string | undefined) ?? 'cmd';
      if (pThread !== thread) return;
      if (mode === 'engineer') {
        const to = packet.to as string | undefined;
        if (to && to !== username) return;
      }
      void load(true);
    });
  }, [mode, side, thread, load, username]);

  useEffect(() => {
    const el = listRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages]);

  const handleSend = async () => {
    if (sending) return;
    if (!text.trim() && !file) return;
    if (canDirectReply && mode === 'commander' && !recipient.trim()) {
      setError('Выберите инженера или нажмите «Ответить» на сообщении');
      return;
    }
    setSending(true);
    setError('');
    try {
      const recipient_username =
        canDirectReply && recipient.trim() ? recipient.trim() : undefined;
      const msg = await sendChatMessage({
        text: text.trim(),
        file,
        side: mode === 'admin' ? side : undefined,
        thread: mode === 'admin' ? thread : canDirectReply ? 'eng' : undefined,
        recipient_username,
      });
      setMessages((prev) => [...prev, msg]);
      lastIdRef.current = msg.id;
      setText('');
      setFile(null);
      setReplyTo(null);
      if (!canDirectReply || mode === 'admin') setRecipient('');
      if (fileRef.current) fileRef.current.value = '';
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  const sideLabel = side === 'A' ? 'ЛК' : 'СБГ';
  const threadLabel = thread === 'eng' ? 'инженеры' : 'командование';

  return (
    <div className={`flex flex-col h-full min-h-0 bg-zinc-950 ${className}`}>
      {mode !== 'engineer' && (
      <div className="shrink-0 px-3 py-2 border-b border-zinc-800 space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-sm font-bold text-zinc-300">Чат</span>
          {mode === 'commander' && (
            <span className={`ml-auto text-xs ${side === 'A' ? 'text-sideA' : 'text-sideB'}`}>
              {thread === 'eng' ? 'отчёты поля' : '↔ штаб'}
            </span>
          )}
        </div>
        {mode === 'commander' && (
          <div className="flex rounded-lg border border-zinc-700 overflow-hidden text-xs w-fit">
            <button
              type="button"
              className={`px-2.5 py-1 ${thread === 'cmd' ? 'bg-zinc-800 text-zinc-200' : 'text-zinc-500'}`}
              onClick={() => setCommanderThread('cmd')}
            >
              Штаб
            </button>
            <button
              type="button"
              className={`px-2.5 py-1 ${thread === 'eng' ? 'bg-zinc-800 text-zinc-200' : 'text-zinc-500'}`}
              onClick={() => setCommanderThread('eng')}
            >
              Инженеры
            </button>
          </div>
        )}
        {mode === 'admin' && (
          <div className="flex flex-wrap gap-1.5">
            {onSideChange && (
              <div className="flex rounded-lg border border-zinc-700 overflow-hidden text-xs">
                <button
                  type="button"
                  className={`px-2.5 py-1 ${side === 'A' ? 'bg-sideA/20 text-sideA' : 'text-zinc-500'}`}
                  onClick={() => onSideChange('A')}
                >
                  ЛК
                </button>
                <button
                  type="button"
                  className={`px-2.5 py-1 ${side === 'B' ? 'bg-sideB/20 text-sideB' : 'text-zinc-500'}`}
                  onClick={() => onSideChange('B')}
                >
                  СБГ
                </button>
              </div>
            )}
            {onThreadChange && (
              <div className="flex rounded-lg border border-zinc-700 overflow-hidden text-xs">
                <button
                  type="button"
                  className={`px-2.5 py-1 ${thread === 'cmd' ? 'bg-zinc-800 text-zinc-200' : 'text-zinc-500'}`}
                  onClick={() => onThreadChange('cmd')}
                >
                  Командование
                </button>
                <button
                  type="button"
                  className={`px-2.5 py-1 ${thread === 'eng' ? 'bg-zinc-800 text-zinc-200' : 'text-zinc-500'}`}
                  onClick={() => onThreadChange('eng')}
                >
                  Инженеры
                </button>
              </div>
            )}
          </div>
        )}
        {mode === 'admin' && (
          <p className="text-[10px] text-zinc-600">
            {sideLabel} · {threadLabel}
          </p>
        )}
      </div>
      )}

      <div ref={listRef} className="flex-1 overflow-y-auto overscroll-contain p-3 space-y-2 min-h-0">
        {messages.length === 0 && (
          <p className="text-center text-sm text-zinc-600 py-8">
            {mode === 'admin'
              ? `Чат: ${sideLabel}, ${threadLabel}`
              : mode === 'engineer'
                ? 'Команды и отчёты со штабом'
                : thread === 'eng'
                  ? 'Отчёты инженеров — нажмите «Ответить» для личного сообщения'
                  : 'Переписка со штабом'}
          </p>
        )}
        {messages.map((msg) => (
          <MessageBubble
            key={msg.id}
            msg={msg}
            mySide={side}
            mine={isMineMessage(msg, mode, username)}
            canReply={canDirectReply}
            onReply={
              canDirectReply && msg.sender_role === 'engineer'
                ? () => setReplyTo(msg.sender_name)
                : undefined
            }
          />
        ))}
      </div>

      <div className="shrink-0 border-t border-zinc-800">
        {!showComposer ? (
          <p className="px-3 py-2 text-xs text-zinc-500 text-center">Нет доступа к отправке</p>
        ) : (
          <>
        {canDirectReply && (
          <div className="px-2 pt-2 space-y-1.5">
            {replyTo && (
              <div className="flex items-center gap-2 text-xs text-zinc-400 bg-zinc-900/80 rounded-lg px-2 py-1.5">
                <span>
                  Ответ: <span className="text-warning font-medium">{replyTo}</span>
                </span>
                <button
                  type="button"
                  className="ml-auto text-zinc-500 hover:text-zinc-300"
                  onClick={() => {
                    setReplyTo(null);
                    setRecipient('');
                  }}
                >
                  ✕
                </button>
              </div>
            )}
            <label className="flex items-center gap-2 text-xs text-zinc-500">
              <span className="shrink-0">Кому:</span>
              <select
                className="input flex-1 py-1 text-xs min-h-0"
                value={recipient}
                onChange={(e) => {
                  setRecipient(e.target.value);
                  setReplyTo(e.target.value || null);
                }}
              >
                {mode === 'admin' && <option value="">Всем инженерам</option>}
                {mode === 'commander' && !recipient && (
                  <option value="">— выберите инженера —</option>
                )}
                {recipients.map((r) => (
                  <option key={r.username} value={r.username}>
                    {r.username}
                  </option>
                ))}
              </select>
            </label>
          </div>
        )}

        {file && (
          <div className="flex items-center gap-2 px-2 pt-2 pb-0.5">
            <div className="flex min-w-0 flex-1 items-center gap-1.5 rounded-md border border-zinc-800 bg-zinc-900/60 px-2 py-1 text-xs text-zinc-300">
              <span className="shrink-0 opacity-70">📎</span>
              <span className="truncate">{file.name}</span>
            </div>
            <button
              type="button"
              className="shrink-0 rounded px-2 py-1 text-xs text-zinc-500 hover:text-zinc-300"
              onClick={() => setFile(null)}
            >
              ✕
            </button>
          </div>
        )}

        {error && <p className="px-2 pt-1 text-xs text-sideB">{error}</p>}

        <div className="flex gap-1.5 items-end p-2">
        <input
          ref={fileRef}
          type="file"
          accept="image/*,video/*"
          className="hidden"
          onChange={(e) => setFile(e.target.files?.[0] ?? null)}
        />
        <button
          type="button"
          className="btn shrink-0 border border-zinc-700 text-lg px-2.5 py-2 min-h-0 leading-none"
          onClick={() => fileRef.current?.click()}
          title="Фото или видео"
        >
          📎
        </button>
        <textarea
          className="input flex-1 text-sm py-2 min-h-[2.5rem] max-h-24 resize-none"
          rows={1}
          placeholder={
            mode === 'engineer'
              ? 'Отчёт штабу…'
              : canDirectReply
                ? recipient
                  ? `Сообщение для ${recipient}…`
                  : 'Сообщение всем инженерам…'
                : 'Сообщение…'
          }
          value={text}
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
              e.preventDefault();
              void handleSend();
            }
          }}
        />
        <button
          type="button"
          className={`btn shrink-0 px-3 py-2 min-h-0 text-sm disabled:opacity-50 ${
            side === 'B' ? 'bg-sideB' : 'bg-sideA'
          } text-white`}
          disabled={sending || (!text.trim() && !file)}
          onClick={() => void handleSend()}
        >
          {sending ? '…' : '→'}
        </button>
        </div>
          </>
        )}
      </div>
    </div>
  );
}
