import type { StatusData } from '../api/client';
import { parseServerUtc } from '../utils/serverDate';

function formatTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const ms = parseServerUtc(iso);
  if (ms == null) return '—';
  return new Date(ms).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

interface Stage1PhaseBannerProps {
  data: StatusData;
  className?: string;
}

export default function Stage1PhaseBanner({ data, className = '' }: Stage1PhaseBannerProps) {
  if (data.current_stage === 3) return null;

  const phase = data.stage1_phase;
  if (!phase || phase === 'idle') {
    return null;
  }

  if (phase === 'hold') {
    const slotNum = (data.stage1_current_slot ?? 0) + 1;
    const slotTotal = data.stage1_slot_count ?? 0;
    const kts = (data.stage1_active_kt_numbers || []).join(', ');
    return (
      <p className={`text-xs text-green-400 ${className}`}>
        Слот {slotNum}
        {slotTotal > 0 ? ` из ${slotTotal}` : ''} до {formatTime(data.stage1_slot_ends_at)} · активные КТ:{' '}
        {kts || '—'}
      </p>
    );
  }

  return (
    <p className={`text-xs text-zinc-500 ${className}`}>
      Расписание этапа 1 завершено
    </p>
  );
}
