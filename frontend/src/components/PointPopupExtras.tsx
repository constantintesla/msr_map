import type { StatusData } from '../api/client';

interface PointPopupExtrasProps {
  point: StatusData['points'][number];
  stage1Phase?: string | null;
}

export default function PointPopupExtras({ point, stage1Phase }: PointPopupExtrasProps) {
  const isHold = stage1Phase === 'hold';

  if (!isHold) return null;

  return (
    <div className="space-y-2 border-t border-zinc-800 pt-2">
      {!point.stage1_capturable && !point.side && (
        <p className="text-xs text-zinc-500">Не в активном наборе слота</p>
      )}
      {point.stage1_capturable && (
        <p className="text-xs text-green-400">
          {point.side ? 'Захвачена — доступна для перезахвата' : 'В активном наборе — можно захватывать'}
        </p>
      )}
    </div>
  );
}
