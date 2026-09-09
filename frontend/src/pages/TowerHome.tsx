import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  dismissTowerOrder,
  fetchActiveTowerOrders,
  fetchTowerChatMessages,
  scanTowerToken,
  sendTowerChatMessage,
  type TowerChatMessage,
  type TowerOrder,
  type TowerScanResult,
} from '../api/client';
import { logout } from '../utils/auth';
import TowerScanResultView from '../components/TowerScanResultView';
import TowerMap from '../components/TowerMap';
import { TOWER_MAP_BY_FACTION } from '../data/towerMapPoints';

export default function TowerHomePage() {
  const navigate = useNavigate();
  const factionName = localStorage.getItem('faction_name') || '';
  const factionCode = localStorage.getItem('faction_code') || '';
  const username = localStorage.getItem('username') || '';
  const [code, setCode] = useState('');
  const [error, setError] = useState('');
  const [result, setResult] = useState<TowerScanResult | null>(null);
  const [loading, setLoading] = useState(false);

  const [orders, setOrders] = useState<TowerOrder[]>([]);
  const [chat, setChat] = useState<TowerChatMessage[]>([]);
  const [chatText, setChatText] = useState('');

  useEffect(() => {
    const load = () => {
      fetchActiveTowerOrders().then(setOrders);
      fetchTowerChatMessages('eng').then((r) => setChat(r.items));
    };
    load();
    const t = setInterval(load, 6000);
    return () => clearInterval(t);
  }, []);

  const handleManualScan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!code.trim()) return;
    setError('');
    setLoading(true);
    try {
      const r = await scanTowerToken(undefined, code.trim());
      setResult(r);
      setCode('');
    } catch (e2) {
      setError(e2 instanceof Error ? e2.message : 'Табличка не найдена');
    } finally {
      setLoading(false);
    }
  };

  const handleSendChat = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chatText.trim()) return;
    await sendTowerChatMessage({ text: chatText.trim(), thread: 'eng' });
    setChatText('');
    fetchTowerChatMessages('eng').then((r) => setChat(r.items));
  };

  return (
    <div className="min-h-dvh flex flex-col p-6 max-w-lg mx-auto">
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold">{factionName || 'Башня'}</h1>
          <p className="text-sm text-zinc-500">{username}</p>
        </div>
        <button type="button" className="text-xs text-zinc-500 underline" onClick={() => logout(navigate)}>
          Выйти
        </button>
      </div>

      <div className="mb-6">
        <TowerMap points={TOWER_MAP_BY_FACTION[factionCode] || []} />
      </div>

      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 mb-6">
        <p className="text-sm text-zinc-300">
          Наведите камеру телефона на QR-табличку — откроется результат прямо в браузере.
        </p>
        {factionCode === 'sbg' && (
          <p className="text-xs text-zinc-500 mt-2">
            На КПП: отсканируйте все три таблички укрепрайона примерно одновременно — начнётся
            удержание.
          </p>
        )}
        {factionCode === 'drg' && (
          <p className="text-xs text-zinc-500 mt-2">
            Скан любой из трёх табличек КПП, пока СБГ удерживает укрепрайон, сбрасывает захват.
          </p>
        )}
      </div>

      <form onSubmit={handleManualScan} className="space-y-2 mb-6">
        <label className="text-xs text-zinc-500">Если камера не сработала — код с таблички</label>
        <div className="flex gap-2">
          <input
            className="input flex-1"
            inputMode="numeric"
            placeholder="Код"
            value={code}
            onChange={(e) => setCode(e.target.value)}
          />
          <button type="submit" className="btn bg-sideA text-white" disabled={loading}>
            {loading ? '…' : 'Ввести'}
          </button>
        </div>
        {error && <p className="text-sideB text-sm">{error}</p>}
      </form>

      {result && <div className="mb-6">
        <TowerScanResultView result={result} />
      </div>}

      {orders.length > 0 && (
        <div className="mb-6 space-y-2">
          <h2 className="text-sm font-semibold text-zinc-200">Приказы командира</h2>
          {orders.map((o) => (
            <div key={o.id} className="rounded-lg border border-warning/50 bg-warning/10 p-3 text-sm">
              <p className="text-zinc-100 font-semibold">{o.target_name}</p>
              <p className="text-xs text-zinc-400 font-mono">
                {o.target_lat.toFixed(6)}, {o.target_lon.toFixed(6)}
              </p>
              {o.note && <p className="text-xs text-zinc-300 mt-1">{o.note}</p>}
              <button
                type="button"
                className="btn text-xs mt-2 border border-zinc-600"
                onClick={async () => {
                  await dismissTowerOrder(o.id);
                  fetchActiveTowerOrders().then(setOrders);
                }}
              >
                Выполнено
              </button>
            </div>
          ))}
        </div>
      )}

      <div className="space-y-2">
        <h2 className="text-sm font-semibold text-zinc-200">Чат со своими</h2>
        <div className="space-y-2 max-h-64 overflow-y-auto">
          {chat.length === 0 && <p className="text-sm text-zinc-500">Сообщений пока нет.</p>}
          {chat.map((m) => (
            <div key={m.id} className="rounded-lg border border-zinc-800 bg-zinc-900 p-2 text-sm">
              <div className="flex items-center gap-2 text-xs text-zinc-500">
                <span>{m.sender_name}</span>
                <span>{new Date(m.created_at).toLocaleTimeString()}</span>
              </div>
              {m.text && <p className="text-zinc-100 mt-0.5 whitespace-pre-wrap">{m.text}</p>}
            </div>
          ))}
        </div>
        <form onSubmit={handleSendChat} className="flex gap-2">
          <input
            className="input flex-1"
            placeholder="Сообщение"
            value={chatText}
            onChange={(e) => setChatText(e.target.value)}
          />
          <button type="submit" className="btn bg-sideA text-white">
            →
          </button>
        </form>
      </div>
    </div>
  );
}
