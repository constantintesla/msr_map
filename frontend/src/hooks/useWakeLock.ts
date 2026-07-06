import { useEffect, useRef } from 'react';

/** Screen Wake Lock API — экран не гаснет на /point и /cache */
export function useWakeLock(enabled: boolean) {
  const sentinelRef = useRef<WakeLockSentinel | null>(null);

  useEffect(() => {
    if (!enabled || !('wakeLock' in navigator)) return;

    let cancelled = false;

    const requestLock = async () => {
      try {
        sentinelRef.current = await navigator.wakeLock.request('screen');
        sentinelRef.current?.addEventListener('release', () => {
          if (!cancelled) requestLock();
        });
      } catch {
        // Wake Lock может быть недоступен
      }
    };

    requestLock();

    const onVisibility = () => {
      if (document.visibilityState === 'visible' && !cancelled) requestLock();
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      cancelled = true;
      document.removeEventListener('visibilitychange', onVisibility);
      sentinelRef.current?.release().catch(() => {});
    };
  }, [enabled]);
}
