import { useEngineerProfile } from '../hooks/useEngineerProfile';

function compactRadioLabel(channel: number | null, frequencyMhz: number | null): string | null {
  if (channel == null) return null;
  if (frequencyMhz != null) return `${channel}·${frequencyMhz.toFixed(3)}`;
  return String(channel);
}

export default function EngineerRadioBadge({ className = '' }: { className?: string }) {
  const profile = useEngineerProfile();
  const compact = compactRadioLabel(profile?.lpd_channel ?? null, profile?.lpd_frequency_mhz ?? null);

  if (!compact) {
    return (
      <span
        className={`shrink-0 text-[10px] font-mono text-zinc-600 ${className}`}
        title="Канал LPD не назначен"
      >
        LPD —
      </span>
    );
  }

  return (
    <span
      className={`shrink-0 text-[10px] font-mono tabular-nums text-zinc-400 ${className}`}
      title={profile?.lpd_label ?? `LPD ${compact}`}
    >
      LPD {compact}
    </span>
  );
}
