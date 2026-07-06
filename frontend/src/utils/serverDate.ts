/** API отдаёт naive UTC без суффикса Z — парсим как UTC, не локальное время. */
export function parseServerUtc(iso: string | null | undefined): number | null {
  if (!iso) return null;
  const trimmed = iso.trim();
  if (!trimmed) return null;
  const hasTz = /[zZ]$|[+-]\d{2}:\d{2}$/.test(trimmed);
  const normalized = hasTz ? trimmed : `${trimmed.replace(' ', 'T')}Z`;
  const ms = Date.parse(normalized);
  return Number.isNaN(ms) ? null : ms;
}

export function secondsUntilDeadline(lastPingIso: string | null | undefined, intervalSec: number): number | null {
  const pingMs = parseServerUtc(lastPingIso);
  if (pingMs == null) return null;
  const deadline = pingMs + intervalSec * 1000;
  return Math.max(0, Math.floor((deadline - Date.now()) / 1000));
}
