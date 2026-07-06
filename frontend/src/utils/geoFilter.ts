import { haversineDistance } from './haversine';

export interface RawGeoFix {
  lat: number;
  lon: number;
  accuracy: number;
  timestamp: number;
  speed: number | null;
}

export interface SmoothedGeoFix {
  lat: number;
  lon: number;
  accuracy: number;
  timestamp: number;
  source: 'raw' | 'smoothed';
}

export type GpsStatus = 'acquiring' | 'good' | 'weak' | 'error';

export const MAX_POOR_ACCURACY_M = 80;
export const OUTLIER_TIME_MS = 8000;
export const OUTLIER_MAX_SPEED_MPS = 2;
export const STATIONARY_SPEED_MPS = 0.5;
export const STATIONARY_MIN_MS = 5000;
export const STATIONARY_MAX_FIXES = 10;
export const STATIONARY_GOOD_ACCURACY_M = 40;
export const STATIONARY_MIN_FIXES = 3;

export interface GeoFilterState {
  smoothed: SmoothedGeoFix | null;
  stationaryFixes: RawGeoFix[];
  stationarySince: number | null;
}

export function createGeoFilterState(): GeoFilterState {
  return { smoothed: null, stationaryFixes: [], stationarySince: null };
}

export function accuracyWeight(accuracy: number): number {
  const a = Math.max(accuracy, 1);
  return 1 / (a * a);
}

export function isMoving(fix: RawGeoFix): boolean {
  return fix.speed !== null && fix.speed >= STATIONARY_SPEED_MPS;
}

export function isOutlier(fix: RawGeoFix, previous: SmoothedGeoFix | null): boolean {
  if (!previous) return false;
  const elapsed = fix.timestamp - previous.timestamp;
  if (elapsed >= OUTLIER_TIME_MS) return false;

  const isStationary = fix.speed === null || fix.speed < OUTLIER_MAX_SPEED_MPS;
  if (!isStationary) return false;

  const dist = haversineDistance(fix.lat, fix.lon, previous.lat, previous.lon);
  const threshold = Math.max(30, 3 * fix.accuracy);
  return dist > threshold;
}

export function smoothFixEma(
  fix: RawGeoFix,
  previous: SmoothedGeoFix | null,
): SmoothedGeoFix | null {
  if (fix.accuracy > MAX_POOR_ACCURACY_M) {
    return null;
  }

  if (isOutlier(fix, previous)) {
    return null;
  }

  if (!previous) {
    return {
      lat: fix.lat,
      lon: fix.lon,
      accuracy: fix.accuracy,
      timestamp: fix.timestamp,
      source: 'raw',
    };
  }

  const wNew = accuracyWeight(fix.accuracy);
  const wPrev = accuracyWeight(previous.accuracy);
  const total = wNew + wPrev;

  return {
    lat: (wNew * fix.lat + wPrev * previous.lat) / total,
    lon: (wNew * fix.lon + wPrev * previous.lon) / total,
    accuracy: fix.accuracy,
    timestamp: fix.timestamp,
    source: 'smoothed',
  };
}

/** @deprecated use processFix */
export function smoothFix(
  fix: RawGeoFix,
  previous: SmoothedGeoFix | null,
): SmoothedGeoFix | null {
  return smoothFixEma(fix, previous);
}

export function weightedAverageFixes(
  fixes: RawGeoFix[],
): { lat: number; lon: number; accuracy: number } {
  let wSum = 0;
  let lat = 0;
  let lon = 0;
  let bestAccuracy = Infinity;

  for (const f of fixes) {
    const w = accuracyWeight(f.accuracy);
    wSum += w;
    lat += w * f.lat;
    lon += w * f.lon;
    bestAccuracy = Math.min(bestAccuracy, f.accuracy);
  }

  return { lat: lat / wSum, lon: lon / wSum, accuracy: bestAccuracy };
}

export function processFix(
  fix: RawGeoFix,
  state: GeoFilterState,
): { result: SmoothedGeoFix | null; state: GeoFilterState } {
  if (isMoving(fix)) {
    state = { ...state, stationaryFixes: [], stationarySince: null };
  }

  const ema = smoothFixEma(fix, state.smoothed);
  if (!ema) {
    return { result: null, state };
  }

  if (!isMoving(fix) && fix.accuracy <= STATIONARY_GOOD_ACCURACY_M) {
    const stationarySince = state.stationarySince ?? fix.timestamp;
    const stationaryFixes = [...state.stationaryFixes, fix].slice(-STATIONARY_MAX_FIXES);
    const nextState: GeoFilterState = {
      smoothed: ema,
      stationaryFixes,
      stationarySince,
    };

    if (
      fix.timestamp - stationarySince >= STATIONARY_MIN_MS &&
      stationaryFixes.length >= STATIONARY_MIN_FIXES
    ) {
      const avg = weightedAverageFixes(stationaryFixes);
      const averaged: SmoothedGeoFix = {
        lat: avg.lat,
        lon: avg.lon,
        accuracy: avg.accuracy,
        timestamp: fix.timestamp,
        source: 'smoothed',
      };
      return { result: averaged, state: { ...nextState, smoothed: averaged } };
    }

    return { result: ema, state: nextState };
  }

  return {
    result: ema,
    state: { smoothed: ema, stationaryFixes: [], stationarySince: null },
  };
}

export function gpsStatusFromAccuracy(accuracy: number | null): GpsStatus {
  if (accuracy === null) return 'acquiring';
  if (accuracy > 40) return 'acquiring';
  if (accuracy > 25) return 'weak';
  return 'good';
}

export function isCaptureAccuracyOk(
  accuracy: number | null | undefined,
  minRequired: number,
): boolean {
  if (!minRequired || minRequired <= 0) return true;
  if (accuracy == null || accuracy <= 0) return false;
  return accuracy <= minRequired;
}
