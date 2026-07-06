import { useState } from 'react';
import type { StatusData } from '../../api/client';
import MobileSheet from '../MobileSheet';

interface AdminQuickNavProps {
  data: StatusData;
  mapSelection: { kind: 'point' | 'cache' | 'landmark'; id: number } | null;
  onSelectPoint: (p: StatusData['points'][number]) => void;
  onSelectCache: (c: StatusData['caches'][number]) => void;
  onForceRelease: (pointId: number) => void;
}

export default function AdminQuickNav({
  data,
  mapSelection,
  onSelectPoint,
  onSelectCache,
  onForceRelease,
}: AdminQuickNavProps) {
  const [open, setOpen] = useState(false);
  const count = data.points.length + data.caches.length;

  if (count === 0) return null;

  return (
    <>
      <button
        type="button"
        className="absolute bottom-3 right-3 z-[1000] pointer-events-auto rounded-full bg-zinc-900/95 border border-zinc-600 px-3 py-2 text-xs font-medium text-zinc-200 shadow-lg active:opacity-80"
        onClick={() => setOpen(true)}
        aria-label="Быстрый переход по точкам"
      >
        Точки · {count}
      </button>

      <MobileSheet open={open} onClose={() => setOpen(false)} title="Быстрый переход" variant="bottom">
        <div className="p-3 flex flex-wrap gap-1">
          {data.points.map((p) => (
            <button
              key={p.id}
              type="button"
              className={`btn text-xs py-1 min-h-0 border ${
                mapSelection?.kind === 'point' && mapSelection.id === p.id
                  ? 'border-sideA bg-sideA/20 text-sideA'
                  : 'border-zinc-700'
              }`}
              onClick={() => {
                onSelectPoint(p);
                setOpen(false);
              }}
            >
              {p.name}
            </button>
          ))}
          {data.caches.map((c) => (
            <button
              key={`c-${c.id}`}
              type="button"
              className={`btn text-xs py-1 min-h-0 border ${
                mapSelection?.kind === 'cache' && mapSelection.id === c.id
                  ? 'border-warning bg-warning/20 text-warning'
                  : 'border-zinc-700'
              }`}
              onClick={() => {
                onSelectCache(c);
                setOpen(false);
              }}
            >
              {c.name}
            </button>
          ))}
          {data.points
            .filter((p) => p.held_by)
            .map((p) => (
              <button
                key={`fr-${p.id}`}
                type="button"
                className="btn text-xs bg-sideB text-white py-1 min-h-0"
                onClick={() => {
                  onForceRelease(p.id);
                  setOpen(false);
                }}
              >
                Сброс {p.id}
              </button>
            ))}
        </div>
      </MobileSheet>
    </>
  );
}
