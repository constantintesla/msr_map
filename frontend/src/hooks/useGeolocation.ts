import { useCallback, useEffect, useRef, useState } from 'react';
import {
  createGeoFilterState,
  gpsStatusFromAccuracy,
  processFix,
  type GeoFilterState,
  type GpsStatus,
  type RawGeoFix,
} from '../utils/geoFilter';

export interface GeoPosition {
  lat: number;
  lon: number;
  accuracy: number;
  timestamp: number;
  source: 'raw' | 'smoothed';
}

export type { GpsStatus };

const GEO_OPTIONS: PositionOptions = {
  enableHighAccuracy: true,
  timeout: 30000,
  maximumAge: 0,
};

export function useGeolocation(enabled = true) {
  const [position, setPosition] = useState<GeoPosition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [gpsStatus, setGpsStatus] = useState<GpsStatus>('acquiring');
  const filterStateRef = useRef<GeoFilterState>(createGeoFilterState());
  const watchIdRef = useRef<number | null>(null);

  const clearWatch = useCallback(() => {
    if (watchIdRef.current !== null && navigator.geolocation) {
      navigator.geolocation.clearWatch(watchIdRef.current);
      watchIdRef.current = null;
    }
  }, []);

  const applyFix = useCallback((pos: GeolocationPosition) => {
    const fix: RawGeoFix = {
      lat: pos.coords.latitude,
      lon: pos.coords.longitude,
      accuracy: pos.coords.accuracy,
      timestamp: pos.timestamp,
      speed: pos.coords.speed,
    };

    const { result, state } = processFix(fix, filterStateRef.current);
    filterStateRef.current = state;

    if (result) {
      setPosition(result);
      setGpsStatus(gpsStatusFromAccuracy(result.accuracy));
      setError(null);
      return;
    }

    if (filterStateRef.current.smoothed) {
      setGpsStatus(gpsStatusFromAccuracy(filterStateRef.current.smoothed.accuracy));
    } else {
      setGpsStatus('acquiring');
    }
  }, []);

  const handleError = useCallback((err: GeolocationPositionError) => {
    setError(err.message);
    setGpsStatus('error');
  }, []);

  const startWatch = useCallback(() => {
    if (!navigator.geolocation) return;
    clearWatch();
    watchIdRef.current = navigator.geolocation.watchPosition(applyFix, handleError, GEO_OPTIONS);
  }, [clearWatch, applyFix, handleError]);

  const refresh = useCallback(() => {
    if (!navigator.geolocation) {
      setError('Геолокация недоступна');
      setGpsStatus('error');
      return;
    }
    filterStateRef.current = createGeoFilterState();
    navigator.geolocation.getCurrentPosition(applyFix, handleError, GEO_OPTIONS);
    startWatch();
  }, [applyFix, handleError, startWatch]);

  useEffect(() => {
    if (!enabled) return;

    if (!navigator.geolocation) {
      setError('Геолокация недоступна');
      setGpsStatus('error');
      return;
    }

    startWatch();

    const onVisibility = () => {
      if (document.visibilityState === 'visible') {
        startWatch();
      }
    };
    document.addEventListener('visibilitychange', onVisibility);

    return () => {
      document.removeEventListener('visibilitychange', onVisibility);
      clearWatch();
    };
  }, [enabled, startWatch, clearWatch]);

  return { position, error, gpsStatus, refresh };
}
