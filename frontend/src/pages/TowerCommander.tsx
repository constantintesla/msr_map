import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  dismissTowerOrder,
  fetchTowerChatMessages,
  fetchTowerChatRecipients,
  fetchTowerOrders,
  fetchTowerRoster,
  sendTowerChatMessage,
  sendTowerOrder,
  type TowerChatMessage,
  type TowerLocation,
  type TowerOrder,
} from '../api/client';
import { logout } from '../utils/auth';

type Tab = 'chat' | 'orders' | 'roster';

export default function TowerCommanderPage() {
  const navigate = useNavigate();
  const factionName = localStorage.getItem('faction_name') || '';
  const username = localStorage.getItem('username') || '';
  const [tab, setTab] = useState<Tab>('chat');

  return (
    <div className="min-h-dvh flex flex-col max-w-lg mx-auto">
      <div className="flex items-center justify-between p-4 border-b border-zinc-800">
        <div>
          <h1 className="text-lg font-bold">{factionName || 'Штаб'}</h1>
          <p className="text-xs text-zinc-500">{username}</p>
        </div>
        <button type="button" className="text-xs text-zinc-500 underline" onClick={() => logout(navigate)}>
          Выйти
        </button>
      </div>

      <div className="flex border-b border-zinc-800">
        {(['chat', 'orders', 'roster'] as Tab[]).map((t) => (
          <button
            key={t}
            type="button"
            className={`flex-1 py-2 text-sm ${tab === t ? 'text-sideA border-b-2 border-sideA' : 'text-zinc-500'}`}
            onClick={() => setTab(t)}
          >
            {t === 'chat' ? 'Чат' : t === 'orders' ? 'Приказы' : 'Ростер'}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto p-4">
        {tab === 'chat' && <ChatTab />}
        {tab === 'orders' && <OrdersTab />}
        {tab === 'roster' && <RosterTab />}
      </div>
    </div>
  );
}

function ChatTab() {
  const [thread, setThread] = useState<'cmd' | 'eng'>('eng');
  const [items, setItems] = useState<TowerChatMessage[]>([]);
  const [text, setText] = useState('');
  const [recipient, setRecipient] = useState('');
  const [recipients, setRecipients] = useState<Array<{ username: string }>>([]);
  const [error, setError] = useState('');

  const load = () => {
    fetchTowerChatMessages(thread).then((r) => setItems(r.items));
  };

  useEffect(() => {
    load();
    fetchTowerChatRecipients().then(setRecipients);
    const t = setInterval(load, 5000);
    return () => clearInterval(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [thread]);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim()) return;
    setError('');
    try {
      await sendTowerChatMessage({ text: text.trim(), thread, recipient_username: recipient || null });
      setText('');
      load();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Не удалось отправить');
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex gap-2 mb-3">
        <button
          type="button"
          className={`btn text-xs flex-1 ${thread === 'eng' ? 'bg-sideA text-white' : 'border border-zinc-600'}`}
          onClick={() => setThread('eng')}
        >
          Свои
        </button>
        <button
          type="button"
          className={`btn text-xs flex-1 ${thread === 'cmd' ? 'bg-sideA text-white' : 'border border-zinc-600'}`}
          onClick={() => setThread('cmd')}
        >
          Штаб/мастер
        </button>
      </div>

      <div className="flex-1 space-y-2 mb-3 min-h-[200px]">
        {items.length === 0 && <p className="text-sm text-zinc-500">Сообщений пока нет.</p>}
        {items.map((m) => (
          <div key={m.id} className="rounded-lg border border-zinc-800 bg-zinc-900 p-2 text-sm">
            <div className="flex items-center gap-2 text-xs text-zinc-500">
              <span>{m.sender_name}</span>
              {m.recipient_username && <span>→ {m.recipient_username}</span>}
              <span>{new Date(m.created_at).toLocaleTimeString()}</span>
            </div>
            {m.text && <p className="text-zinc-100 mt-0.5 whitespace-pre-wrap">{m.text}</p>}
          </div>
        ))}
      </div>

      <form onSubmit={handleSend} className="space-y-2">
        {thread === 'eng' && recipients.length > 0 && (
          <select
            className="input text-sm"
            value={recipient}
            onChange={(e) => setRecipient(e.target.value)}
          >
            <option value="">Всем своим</option>
            {recipients.map((r) => (
              <option key={r.username} value={r.username}>
                {r.username}
              </option>
            ))}
          </select>
        )}
        <div className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="Сообщение"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
          <button type="submit" className="btn bg-sideA text-white">
            →
          </button>
        </div>
        {error && <p className="text-sideB text-sm">{error}</p>}
      </form>
    </div>
  );
}

function OrdersTab() {
  const [orders, setOrders] = useState<TowerOrder[]>([]);
  const [targetUsername, setTargetUsername] = useState('');
  const [targetName, setTargetName] = useState('');
  const [lat, setLat] = useState('');
  const [lon, setLon] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState('');

  const load = () => {
    fetchTowerOrders().then(setOrders);
  };

  useEffect(() => {
    load();
    const t = setInterval(load, 8000);
    return () => clearInterval(t);
  }, []);

  const handleSend = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    const latN = Number(lat);
    const lonN = Number(lon);
    if (!targetUsername.trim() || !targetName.trim() || Number.isNaN(latN) || Number.isNaN(lonN)) {
      setError('Заполните позывной, название точки и координаты');
      return;
    }
    try {
      await sendTowerOrder({
        target_username: targetUsername.trim(),
        target_name: targetName.trim(),
        target_lat: latN,
        target_lon: lonN,
        note: note.trim() || undefined,
      });
      setTargetUsername('');
      setTargetName('');
      setLat('');
      setLon('');
      setNote('');
      load();
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Не удалось отправить приказ');
    }
  };

  const handleDismiss = async (id: number) => {
    await dismissTowerOrder(id);
    load();
  };

  return (
    <div className="space-y-4">
      <form onSubmit={handleSend} className="space-y-2 rounded-lg border border-zinc-800 p-3">
        <p className="text-sm font-semibold text-zinc-200">Новый приказ</p>
        <input
          className="input text-sm"
          placeholder="Позывной игрока"
          value={targetUsername}
          onChange={(e) => setTargetUsername(e.target.value)}
        />
        <input
          className="input text-sm"
          placeholder="Название точки"
          value={targetName}
          onChange={(e) => setTargetName(e.target.value)}
        />
        <div className="flex gap-2">
          <input className="input text-sm flex-1" placeholder="lat" value={lat} onChange={(e) => setLat(e.target.value)} />
          <input className="input text-sm flex-1" placeholder="lon" value={lon} onChange={(e) => setLon(e.target.value)} />
        </div>
        <input
          className="input text-sm"
          placeholder="Примечание (необязательно)"
          value={note}
          onChange={(e) => setNote(e.target.value)}
        />
        {error && <p className="text-sideB text-sm">{error}</p>}
        <button type="submit" className="btn bg-sideA text-white text-sm w-full">
          Отправить приказ
        </button>
      </form>

      <div className="space-y-2">
        {orders.map((o) => (
          <div key={o.id} className="rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-sm">
            <div className="flex items-center justify-between">
              <span className="font-semibold">{o.target_username}</span>
              <span className={o.dismissed ? 'text-zinc-500' : 'text-warning'}>
                {o.dismissed ? 'принято' : 'ожидание'}
              </span>
            </div>
            <p className="text-zinc-300">{o.target_name}</p>
            <p className="text-xs text-zinc-500 font-mono">
              {o.target_lat.toFixed(6)}, {o.target_lon.toFixed(6)}
            </p>
            {o.note && <p className="text-xs text-zinc-400 mt-1">{o.note}</p>}
            {!o.dismissed && (
              <button
                type="button"
                className="btn text-xs mt-2 border border-zinc-600"
                onClick={() => void handleDismiss(o.id)}
              >
                Отметить выполненным
              </button>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

function RosterTab() {
  const [roster, setRoster] = useState<TowerLocation[]>([]);

  useEffect(() => {
    const load = () => fetchTowerRoster().then(setRoster);
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, []);

  if (roster.length === 0) {
    return <p className="text-sm text-zinc-500">Пока никто не прислал координаты.</p>;
  }

  return (
    <div className="space-y-2">
      {roster.map((r) => (
        <a
          key={r.user_id}
          className="block rounded-lg border border-zinc-800 bg-zinc-900 p-3 text-sm active:bg-zinc-800"
          href={`https://maps.google.com/?q=${r.lat},${r.lon}`}
          target="_blank"
          rel="noreferrer"
        >
          <div className="flex items-center justify-between">
            <span className="font-semibold">{r.username}</span>
            <span className="text-xs text-zinc-500">{new Date(r.updated_at).toLocaleTimeString()}</span>
          </div>
          <p className="text-xs text-zinc-500 font-mono">
            {r.lat.toFixed(6)}, {r.lon.toFixed(6)} · ±{Math.round(r.accuracy)}м
          </p>
        </a>
      ))}
    </div>
  );
}
