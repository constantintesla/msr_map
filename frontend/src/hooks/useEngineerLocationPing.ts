import { useEffect, useRef } from 'react';
import { pingEngineerLocation } from '../api/client';
import { haversineDistance } from '../utils/haversine';
import type { GeoPosition } from './useGeolocation';

const PING_INTERVAL_MS = 8000;
const PING_THROTTLE_MS = 6000;
const MOVE_THRESHOLD_M = 3;

export function useEngineerLocationPing(position: GeoPosition | null) {
  const lastSent = useRef(0);
  const lastSentPos = useRef<{ lat: number; lon: number } | null>(null);

  useEffect(() => {
    if (!position) return;
    const role = localStorage.getItem('role');
    if (role !== 'engineer') return;

    const send = (force = false) => {
      const now = Date.now();
      const moved =
        lastSentPos.current == null ||
        haversineDistance(
          position.lat,
          position.lon,
          lastSentPos.current.lat,
          lastSentPos.current.lon
        ) > MOVE_THRESHOLD_M;
      const throttled = now - lastSent.current < PING_THROTTLE_MS;

      if (!force && throttled && !moved) return;

      lastSent.current = now;
      lastSentPos.current = { lat: position.lat, lon: position.lon };
      pingEngineerLocation(position.lat, position.lon, position.accuracy).catch(() => {});
    };

    send(lastSent.current === 0);
    const id = setInterval(() => send(false), PING_INTERVAL_MS);
    return () => clearInterval(id);
  }, [position?.lat, position?.lon, position?.accuracy]);
}
