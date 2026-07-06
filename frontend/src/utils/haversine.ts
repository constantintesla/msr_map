/** Haversine: расстояние в метрах, R = 6371000 */
export function haversineDistance(
  lat1: number,
  lon1: number,
  lat2: number,
  lon2: number
): number {
  const R = 6371000;
  const toRad = (deg: number) => (deg * Math.PI) / 180;
  const dLat = toRad(lat2 - lat1);
  const dLon = toRad(lon2 - lon1);
  const a =
    Math.sin(dLat / 2) ** 2 +
    Math.cos(toRad(lat1)) * Math.cos(toRad(lat2)) * Math.sin(dLon / 2) ** 2;
  return R * 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
}

/** Fallback до загрузки capture_radius_m из /api/status */
export const FENCE_RADIUS_M = 15;

export const ACCURACY_FENCE_BONUS_MAX_M = 20;

export function effectiveFenceRadius(
  radiusM: number,
  accuracy?: number,
  bonusMaxM = ACCURACY_FENCE_BONUS_MAX_M,
): number {
  const cap = Math.max(0, bonusMaxM);
  const bonus = accuracy != null && accuracy > 0 ? Math.min(accuracy, cap) : 0;
  return radiusM + bonus;
}

export function isInsideFence(
  userLat: number,
  userLon: number,
  targetLat: number,
  targetLon: number,
  radiusM = FENCE_RADIUS_M
): boolean {
  return haversineDistance(userLat, userLon, targetLat, targetLon) <= radiusM;
}

export function isInsideFenceWithAccuracy(
  userLat: number,
  userLon: number,
  targetLat: number,
  targetLon: number,
  radiusM = FENCE_RADIUS_M,
  accuracy?: number,
  bonusMaxM = ACCURACY_FENCE_BONUS_MAX_M,
): boolean {
  return (
    haversineDistance(userLat, userLon, targetLat, targetLon) <=
    effectiveFenceRadius(radiusM, accuracy, bonusMaxM)
  );
}
