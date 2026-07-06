import { useEngineerOrders } from '../context/EngineerOrdersContext';

interface EngineerOrderBannerProps {
  className?: string;
  onShowOnMap?: () => void;
}

export default function EngineerOrderBanner({ className = '', onShowOnMap }: EngineerOrderBannerProps) {
  const { latest, dismiss } = useEngineerOrders();

  if (!latest) return null;

  const kindLabel = latest.target_kind === 'point' ? 'точку' : 'ящик';

  return (
    <div
      className={`rounded-lg border border-warning/40 bg-warning/10 px-3 py-2 text-sm ${className}`}
      role="status"
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0 text-left">
          <p className="text-[10px] uppercase tracking-wide text-warning font-bold">Приказ</p>
          <p className="text-zinc-200 mt-0.5">
            На {kindLabel}: <span className="font-medium">{latest.target_name}</span>
          </p>
          {latest.note && <p className="text-xs text-zinc-400 mt-1">{latest.note}</p>}
        </div>
        <button
          type="button"
          className="shrink-0 text-zinc-500 hover:text-zinc-300 px-1"
          title="Скрыть приказ"
          onClick={() => void dismiss(latest.id)}
        >
          ✕
        </button>
      </div>
      <div className="flex flex-wrap gap-2 mt-2">
        {onShowOnMap && (
          <button
            type="button"
            className="btn text-xs min-h-0 py-1 px-2 border border-warning/50 text-warning"
            onClick={onShowOnMap}
          >
            На карте
          </button>
        )}
        <button
          type="button"
          className="btn text-xs min-h-0 py-1 px-2 border border-zinc-700 text-zinc-400"
          onClick={() => void dismiss(latest.id)}
        >
          Понял
        </button>
      </div>
    </div>
  );
}
