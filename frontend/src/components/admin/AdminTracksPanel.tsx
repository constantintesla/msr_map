import { useCallback, useEffect, useState } from 'react';
import type { MovementTracksData, StatusData } from '../../api/client';
import { exportMovementTracks, fetchMovementTracks } from '../../api/client';
import GameMap from '../GameMap';
import { engineerColor } from '../../utils/engineerColor';

interface AdminTracksPanelProps {
  data: StatusData;
  onClose: () => void;
}

function formatSessionStart(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '—';
  return d.toLocaleString('ru-RU', { day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
}

export default function AdminTracksPanel({ data, onClose }: AdminTracksPanelProps) {
  const [tracksData, setTracksData] = useState<MovementTracksData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [hiddenUsers, setHiddenUsers] = useState<Set<number>>(() => new Set());
  const [exporting, setExporting] = useState(false);

  const load = useCallback(() => {
    fetchMovementTracks()
      .then((res) => {
        setTracksData(res);
        setError('');
      })
      .catch((e) => setError(e instanceof Error ? e.message : 'Ошибка загрузки треков'))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const id = setInterval(load, 5000);
    return () => clearInterval(id);
  }, [load]);

  const visibleTracks = (tracksData?.tracks ?? []).filter((t) => !hiddenUsers.has(t.user_id));

  const toggleUser = (userId: number) => {
    setHiddenUsers((prev) => {
      const next = new Set(prev);
      if (next.has(userId)) next.delete(userId);
      else next.add(userId);
      return next;
    });
  };

  const handleExport = async () => {
    setExporting(true);
    try {
      await exportMovementTracks();
      setError('');
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка экспорта');
    } finally {
      setExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-zinc-950 no-print">
      <header className="shrink-0 flex flex-wrap items-center gap-2 px-3 py-2 border-b border-zinc-800 bg-zinc-900/95">
        <div className="flex-1 min-w-0">
          <h2 className="font-bold text-base text-zinc-100">Треки передвижения</h2>
          <p className="text-xs text-zinc-500 mt-0.5">
            Сессия #{tracksData?.game_session_id ?? '…'}
            {tracksData?.game_started_at ? ` · старт ${formatSessionStart(tracksData.game_started_at)}` : ''}
            {tracksData ? ` · ${tracksData.total_points} точек` : ''}
          </p>
        </div>
        <button
          type="button"
          className="btn border border-zinc-600 text-sm"
          disabled={exporting || !tracksData?.total_points}
          onClick={() => void handleExport()}
        >
          {exporting ? '…' : 'CSV'}
        </button>
        <button type="button" className="btn border border-zinc-600 text-sm" onClick={onClose}>
          Закрыть
        </button>
      </header>

      {error && <p className="shrink-0 px-3 py-1 text-xs text-sideB">{error}</p>}

      <div className="flex-1 flex flex-col md:flex-row min-h-0">
        <aside className="shrink-0 md:w-56 border-b md:border-b-0 md:border-r border-zinc-800 bg-zinc-900/50 max-h-[28vh] md:max-h-none overflow-y-auto">
          <div className="p-2 space-y-1">
            <p className="text-[10px] uppercase tracking-wide text-zinc-600 px-1 mb-1">Инженеры</p>
            {loading && !tracksData && <p className="text-xs text-zinc-500 px-1">Загрузка…</p>}
            {!loading && (tracksData?.tracks.length ?? 0) === 0 && (
              <p className="text-xs text-zinc-500 px-1">
                {data.game_status === 'idle'
                  ? 'Нет данных. Запустите игру — GPS будет записываться автоматически.'
                  : 'Пока нет точек. Инженеры должны открыть карту с включённым GPS.'}
              </p>
            )}
            {(tracksData?.tracks ?? []).map((track) => {
              const color = engineerColor(track.username);
              const hidden = hiddenUsers.has(track.user_id);
              const sideLabel = track.side === 'A' ? 'ЛК' : 'СБГ';
              return (
                <button
                  key={track.user_id}
                  type="button"
                  className={`w-full flex items-center gap-2 rounded-lg px-2 py-1.5 text-left text-xs transition-colors ${
                    hidden ? 'opacity-40 bg-transparent' : 'bg-zinc-800/60 hover:bg-zinc-800'
                  }`}
                  onClick={() => toggleUser(track.user_id)}
                  title={hidden ? 'Показать трек' : 'Скрыть трек'}
                >
                  <span
                    className="w-3 h-3 rounded-full shrink-0 border border-white/20"
                    style={{ backgroundColor: color }}
                    aria-hidden
                  />
                  <span className="flex-1 min-w-0 truncate text-zinc-200">{track.label}</span>
                  <span className={`shrink-0 text-[10px] ${track.side === 'A' ? 'text-sideA' : 'text-sideB'}`}>
                    {sideLabel}
                  </span>
                  <span className="shrink-0 tabular-nums text-zinc-500">{track.points.length}</span>
                </button>
              );
            })}
          </div>
        </aside>

        <div className="flex-1 min-h-0 relative map-page">
          <GameMap
            data={data}
            showRadii={false}
            autoFitBounds
            movementTracks={visibleTracks}
          />
        </div>
      </div>
    </div>
  );
}
