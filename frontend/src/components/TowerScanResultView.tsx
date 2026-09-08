import { useEffect, useState } from 'react';
import type { TowerScanResult } from '../api/client';

function CountdownLabel({ endsAt }: { endsAt: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);
  const remainingMs = new Date(endsAt).getTime() - now;
  if (remainingMs <= 0) return <span>0:00</span>;
  const totalSec = Math.floor(remainingMs / 1000);
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return (
    <span>
      {m}:{String(s).padStart(2, '0')}
    </span>
  );
}

const ZONE_LABEL: Record<string, string> = {
  idle: 'Ожидание',
  syncing: 'Синхронизация…',
  holding: 'Удержание',
  captured: 'Взят',
};

export default function TowerScanResultView({ result }: { result: TowerScanResult }) {
  if (result.kind === 'village') {
    const d = result.data;
    return (
      <div className="rounded-lg border border-zinc-700 bg-zinc-950 p-4 space-y-3">
        <h2 className="text-lg font-bold text-sideA">{d.target_faction_name}</h2>
        {(d.elder_note || d.elder_photo_url) && (
          <div className="space-y-2">
            {d.elder_photo_url && (
              <img src={d.elder_photo_url} alt="Старейшина" className="rounded-lg max-h-64 w-full object-cover" />
            )}
            {d.elder_note && <p className="text-sm text-zinc-200 whitespace-pre-wrap">{d.elder_note}</p>}
          </div>
        )}
        {d.drop_lat != null && d.drop_lon != null && (
          <p className="text-sm text-zinc-300">
            Координата закладки: <span className="font-mono">{d.drop_lat.toFixed(6)}, {d.drop_lon.toFixed(6)}</span>
          </p>
        )}
        {d.cache_targets && (
          <div>
            <p className="text-sm text-zinc-400 mb-1">
              Раскрыто координат: {d.revealed_count ?? d.cache_targets.length} из {d.total_targets ?? '?'}
            </p>
            {d.cache_targets.length === 0 ? (
              <p className="text-sm text-zinc-500">Пока ничего не раскрыто — попробуйте позже.</p>
            ) : (
              <ul className="space-y-1">
                {d.cache_targets.map((t) => (
                  <li key={t.name} className="text-sm font-mono text-zinc-200">
                    {t.name}: {t.lat.toFixed(6)}, {t.lon.toFixed(6)}
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
    );
  }

  const z = result.data;
  return (
    <div className="rounded-lg border border-zinc-700 bg-zinc-950 p-4 space-y-2">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-bold text-sideA">{z.zone_name}</h2>
        <span className="text-sm uppercase tracking-wide text-zinc-300">{ZONE_LABEL[z.status] || z.status}</span>
      </div>
      <div className="flex flex-wrap gap-2 text-sm">
        {z.points.map((p) => (
          <span
            key={p.id}
            className={`px-2 py-1 rounded border ${p.scanned ? 'border-sideA text-sideA' : 'border-zinc-700 text-zinc-500'}`}
          >
            {p.name}
          </span>
        ))}
      </div>
      {z.status === 'holding' && z.hold_ends_at && (
        <p className="text-sm text-warning">
          До взятия УР: <CountdownLabel endsAt={z.hold_ends_at} />
        </p>
      )}
      {z.status === 'captured' && <p className="text-sm text-sideA">Укрепрайон взят.</p>}
    </div>
  );
}
