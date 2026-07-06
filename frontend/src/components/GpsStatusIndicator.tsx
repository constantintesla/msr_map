import type { GpsStatus } from '../hooks/useGeolocation';

const STATUS_STYLES: Record<GpsStatus, string> = {
  good: 'text-green-400',
  weak: 'text-warning',
  acquiring: 'text-zinc-400',
  error: 'text-sideB',
};

const STATUS_LABELS: Record<GpsStatus, string> = {
  good: 'GPS',
  weak: 'GPS (слабый)',
  acquiring: 'GPS (поиск…)',
  error: 'GPS (ошибка)',
};

export interface GpsStatusIndicatorProps {
  gpsStatus: GpsStatus;
  accuracy: number | null;
  error?: string | null;
  onRefresh?: () => void;
  captureBlocked?: boolean;
  minCaptureAccuracy?: number;
}

export default function GpsStatusIndicator({
  gpsStatus,
  accuracy,
  error,
  onRefresh,
  captureBlocked,
  minCaptureAccuracy,
}: GpsStatusIndicatorProps) {
  const showHint = gpsStatus === 'acquiring' || gpsStatus === 'weak';

  return (
    <div className="space-y-1">
      <div className="flex items-center gap-2 flex-wrap">
        <p className={`text-sm font-mono tabular-nums ${STATUS_STYLES[gpsStatus]}`}>
          {STATUS_LABELS[gpsStatus]}
          {accuracy != null && accuracy > 0 ? ` · ±${Math.round(accuracy)}м` : ''}
        </p>
        {onRefresh && (
          <button
            type="button"
            className="text-xs text-zinc-400 underline hover:text-zinc-200"
            onClick={onRefresh}
          >
            Обновить GPS
          </button>
        )}
      </div>
      {showHint && (
        <p className="text-xs text-zinc-500">
          Держите телефон на открытом месте, подождите уточнения GPS
        </p>
      )}
      {captureBlocked && minCaptureAccuracy && minCaptureAccuracy > 0 && (
        <p className="text-xs text-warning">
          Для захвата нужна точность ≤{minCaptureAccuracy}м
          {accuracy != null && accuracy > 0 ? ` (сейчас ±${Math.round(accuracy)}м)` : ''}
        </p>
      )}
      {error && <p className="text-sideB text-sm">{error}</p>}
    </div>
  );
}
