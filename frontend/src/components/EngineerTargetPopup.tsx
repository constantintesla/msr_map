import type { StatusData } from '../api/client';
import PointPopupExtras from './PointPopupExtras';

interface EngineerTargetPopupProps {
  kind: 'point' | 'cache';
  data: StatusData['points'][number] | StatusData['caches'][number];
  orderNote?: string | null;
  stage1Phase?: string | null;
  side?: string;
  onClose: () => void;
  onOpenCapture: () => void;
}

export default function EngineerTargetPopup({
  kind,
  data,
  orderNote,
  stage1Phase,
  onClose,
  onOpenCapture,
}: EngineerTargetPopupProps) {
  const kindLabel = kind === 'point' ? 'Точка' : 'Ящик';
  const point = kind === 'point' ? (data as StatusData['points'][number]) : null;
  const cache = kind === 'cache' ? (data as StatusData['caches'][number]) : null;
  const qrOnlyLoot = cache?.cache_kind === 'film_loot';

  const canCapture =
    kind !== 'point' || stage1Phase === 'hold' || !!point?.stage1_capturable || !!point?.side;

  return (
    <div className="text-sm space-y-2 min-w-[200px]">
      <div>
        <p className="text-[10px] uppercase tracking-wide text-zinc-500">{kindLabel}</p>
        <p className="font-bold text-zinc-100">{data.name}</p>
        <p className="text-xs text-zinc-500 font-mono mt-0.5">
          {data.lat.toFixed(5)}, {data.lon.toFixed(5)}
        </p>
      </div>

      {orderNote && (
        <p className="text-xs text-warning border-l-2 border-warning/50 pl-2">{orderNote}</p>
      )}

      {qrOnlyLoot && (
        <p className="text-xs text-zinc-400 border-l-2 border-warning/40 pl-2">
          Взлом только через QR на табличке. Подойдите к объекту и отсканируйте QR.
        </p>
      )}

      {point && <PointPopupExtras point={point} stage1Phase={stage1Phase} />}

      <div className="flex flex-wrap gap-2 pt-1">
        {!qrOnlyLoot && (
          <button
            type="button"
            className="btn flex-1 bg-sideA text-white text-xs min-h-0 py-2 disabled:opacity-40"
            disabled={kind === 'point' && !canCapture && !point?.side}
            onClick={onOpenCapture}
          >
            {kind === 'point' ? 'Захват' : 'Действия'}
          </button>
        )}

        <button
          type="button"
          className="btn border border-zinc-700 text-xs min-h-0 py-2 px-3"
          onClick={onClose}
        >
          Закрыть
        </button>
      </div>
    </div>
  );
}
