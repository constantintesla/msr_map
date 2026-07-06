import type { GeoPosition } from '../hooks/useGeolocation';

export function applyGpsOffset(
  position: GeoPosition | null,
  latOffset = 0,
  lonOffset = 0,
): GeoPosition | null {
  if (!position) return null;
  if (latOffset === 0 && lonOffset === 0) return position;
  return {
    ...position,
    lat: position.lat + latOffset,
    lon: position.lon + lonOffset,
  };
}
