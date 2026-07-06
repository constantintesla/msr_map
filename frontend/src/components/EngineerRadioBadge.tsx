import { useEngineerProfile } from '../hooks/useEngineerProfile';

export default function EngineerRadioBadge({ className = '' }: { className?: string }) {
  const profile = useEngineerProfile();

  if (!profile?.lpd_label) {
    return (
      <span
        className={`inline-flex items-center rounded-md border border-zinc-800 bg-zinc-900/80 px-2 py-0.5 text-[11px] text-zinc-500 ${className}`}
      >
        📻 канал не назначен
      </span>
    );
  }

  return (
    <span
      className={`inline-flex items-center gap-1 rounded-md border border-zinc-700 bg-zinc-900 px-2 py-0.5 text-[11px] font-medium text-zinc-200 ${className}`}
      title={profile.lpd_label}
    >
      <span className="opacity-70">📻</span>
      {profile.lpd_label}
    </span>
  );
}
