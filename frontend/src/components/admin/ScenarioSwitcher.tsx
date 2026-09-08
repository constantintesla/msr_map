import { useState } from 'react';
import type { Scenario } from '../../api/client';

interface ScenarioSwitcherProps {
  scenarios: Scenario[];
  loading: boolean;
  error: string;
  onCreate: (name: string) => void | Promise<void>;
  onActivate: (id: number) => void | Promise<void>;
  onArchive: (id: number) => void | Promise<void>;
}

export default function ScenarioSwitcher({
  scenarios,
  loading,
  error,
  onCreate,
  onActivate,
  onArchive,
}: ScenarioSwitcherProps) {
  const [newName, setNewName] = useState('');
  const [creating, setCreating] = useState(false);

  const handleCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setCreating(true);
    try {
      await onCreate(name);
      setNewName('');
    } finally {
      setCreating(false);
    }
  };

  return (
    <div className="no-print p-4 space-y-4">
      <div>
        <h2 className="text-base font-bold text-sideA">Сценарии (мероприятия)</h2>
        <p className="text-sm text-zinc-400 mt-0.5">
          Активен всегда один сценарий — свои точки, схроны, настройки и счёт. Переключение
          сбрасывает текущие приказы и позиции инженеров на карте.
        </p>
      </div>

      {error && <p className="text-sm text-sideB">{error}</p>}

      <div className="flex flex-wrap items-end gap-2">
        <label className="text-xs text-zinc-400 flex-1 min-w-[200px]">
          Название нового сценария
          <input
            className="input block mt-1 w-full min-h-0 py-1.5 text-sm"
            value={newName}
            placeholder="Например, «Мероприятие 2»"
            onChange={(e) => setNewName(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void handleCreate();
            }}
          />
        </label>
        <button
          type="button"
          className="btn bg-sideA text-white text-sm disabled:opacity-50"
          disabled={creating || !newName.trim()}
          onClick={() => void handleCreate()}
        >
          {creating ? '…' : 'Создать'}
        </button>
      </div>

      <ul className="space-y-2">
        {loading && scenarios.length === 0 && (
          <li className="text-sm text-zinc-500">Загрузка сценариев…</li>
        )}
        {scenarios.map((s) => (
          <li
            key={s.id}
            className={`rounded-lg border px-3 py-2 flex flex-wrap items-center justify-between gap-2 ${
              s.is_active ? 'border-sideA bg-sideA/10' : 'border-zinc-700 bg-zinc-950'
            }`}
          >
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                <span className="font-semibold text-zinc-100">{s.name}</span>
                {s.is_active && (
                  <span className="text-[10px] uppercase tracking-wide text-sideA border border-sideA/50 rounded px-1.5 py-0.5">
                    активен
                  </span>
                )}
              </div>
              <span className="text-xs text-zinc-500 font-mono">{s.slug}</span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              {!s.is_active && (
                <button
                  type="button"
                  className="btn text-sm border border-sideA text-sideA"
                  onClick={() => void onActivate(s.id)}
                >
                  Активировать
                </button>
              )}
              {!s.is_active && (
                <button
                  type="button"
                  className="btn text-sm border border-zinc-600 text-zinc-400"
                  onClick={() => void onArchive(s.id)}
                >
                  Архивировать
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
