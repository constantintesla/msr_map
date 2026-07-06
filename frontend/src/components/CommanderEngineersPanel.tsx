import { useCallback, useEffect, useState } from 'react';
import {
  assignEngineerLpdChannel,
  fetchCommanderEngineers,
  fetchLpdChannels,
  type EngineerPoolItem,
  type LpdChannel,
} from '../api/client';

interface CommanderEngineersPanelProps {
  side: 'A' | 'B';
}

export default function CommanderEngineersPanel({ side }: CommanderEngineersPanelProps) {
  const [engineers, setEngineers] = useState<EngineerPoolItem[]>([]);
  const [channels, setChannels] = useState<LpdChannel[]>([]);
  const [error, setError] = useState('');
  const [savingId, setSavingId] = useState<number | null>(null);

  const load = useCallback(() => {
    Promise.all([fetchCommanderEngineers(), fetchLpdChannels()])
      .then(([eng, ch]) => {
        setEngineers(eng);
        setChannels(ch);
        setError('');
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Ошибка загрузки'));
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const handleChannel = async (eng: EngineerPoolItem, value: string) => {
    const channel = value === '' ? null : Number(value);
    setSavingId(eng.id);
    try {
      const updated = await assignEngineerLpdChannel(eng.id, channel);
      setEngineers((prev) => prev.map((e) => (e.id === eng.id ? updated : e)));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setSavingId(null);
    }
  };

  const sideLabel = side === 'A' ? 'ЛК' : 'СБГ';
  const sideColor = side === 'A' ? 'text-sideA' : 'text-sideB';

  return (
    <div className="p-3 space-y-3">
      <div>
        <h2 className={`text-sm font-bold ${sideColor}`}>Пул инженеров · {sideLabel}</h2>
        <p className="text-xs text-zinc-500 mt-0.5">
          Выдайте логин/пароль полевым инженерам и назначьте канал LPD (433 МГц).
        </p>
      </div>

      {error && <p className="text-xs text-sideB">{error}</p>}

      <div className="hidden md:block overflow-x-auto rounded-xl border border-zinc-800">
        <table className="w-full text-xs">
          <thead>
            <tr className="border-b border-zinc-800 bg-zinc-900/80 text-zinc-500 text-left">
              <th className="px-2 py-2 font-medium">#</th>
              <th className="px-2 py-2 font-medium">Логин</th>
              <th className="px-2 py-2 font-medium">Пароль</th>
              <th className="px-2 py-2 font-medium min-w-[9rem]">LPD канал</th>
            </tr>
          </thead>
          <tbody>
            {engineers.map((eng, idx) => (
              <tr key={eng.id} className="border-b border-zinc-800/80 last:border-0">
                <td className="px-2 py-2 text-zinc-500">{idx + 1}</td>
                <td className="px-2 py-2 font-mono text-zinc-200">{eng.username}</td>
                <td className="px-2 py-2 font-mono text-zinc-400">{eng.password_hint}</td>
                <td className="px-2 py-2">
                  <select
                    className="input w-full min-h-0 py-1 text-xs"
                    value={eng.lpd_channel ?? ''}
                    disabled={savingId === eng.id}
                    onChange={(e) => void handleChannel(eng, e.target.value)}
                  >
                    <option value="">— не назначен —</option>
                    {channels.map((ch) => (
                      <option key={ch.channel} value={ch.channel}>
                        {ch.channel} · {ch.frequency_mhz.toFixed(3)} МГц
                      </option>
                    ))}
                  </select>
                </td>
              </tr>
            ))}
            {engineers.length === 0 && (
              <tr>
                <td colSpan={4} className="px-3 py-6 text-center text-zinc-600">
                  Нет инженеров — настройте количество в админке
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <ul className="md:hidden space-y-2">
        {engineers.map((eng, idx) => (
          <li key={eng.id} className="rounded-xl border border-zinc-800 bg-zinc-900/50 p-3 space-y-2">
            <div className="flex items-center justify-between gap-2">
              <span className="text-xs text-zinc-500">#{idx + 1}</span>
              <span className="font-mono text-sm text-zinc-200 truncate">{eng.username}</span>
            </div>
            <div className="flex items-center gap-2 text-xs">
              <span className="text-zinc-500 shrink-0">Пароль</span>
              <span className="font-mono text-zinc-400 truncate">{eng.password_hint}</span>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wide text-zinc-500 block mb-1">
                LPD канал
              </label>
              <select
                className="input w-full !min-h-0 py-1.5 text-xs"
                value={eng.lpd_channel ?? ''}
                disabled={savingId === eng.id}
                onChange={(e) => void handleChannel(eng, e.target.value)}
              >
                <option value="">— не назначен —</option>
                {channels.map((ch) => (
                  <option key={ch.channel} value={ch.channel}>
                    {ch.channel} · {ch.frequency_mhz.toFixed(3)} МГц
                  </option>
                ))}
              </select>
            </div>
          </li>
        ))}
        {engineers.length === 0 && (
          <li className="rounded-xl border border-zinc-800 px-3 py-6 text-center text-zinc-600 text-sm">
            Нет инженеров — настройте количество в админке
          </li>
        )}
      </ul>

      <details className="text-xs text-zinc-500">
        <summary className="cursor-pointer text-zinc-400 hover:text-zinc-300">Справка LPD 433 МГц</summary>
        <p className="mt-2 leading-relaxed">
          Диапазон маломощных раций LPD: каналы 1–69, 433.075–434.775 МГц, шаг 25 кГц. Назначайте разные каналы
          соседним группам, чтобы не создавать помехи.
        </p>
      </details>
    </div>
  );
}
