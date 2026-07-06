import { describe, expect, it } from 'vitest';
import {
  createGeoFilterState,
  isOutlier,
  processFix,
  smoothFix,
  type RawGeoFix,
  type SmoothedGeoFix,
} from './geoFilter';

const baseTs = 1_700_000_000_000;

function rawFix(
  lat: number,
  lon: number,
  accuracy: number,
  timestamp = baseTs,
  speed: number | null = 0,
): RawGeoFix {
  return { lat, lon, accuracy, timestamp, speed };
}

describe('isOutlier', () => {
  const previous: SmoothedGeoFix = {
    lat: 44.529392,
    lon: 132.828296,
    accuracy: 10,
    timestamp: baseTs,
    source: 'raw',
  };

  it('rejects a sudden jump while stationary', () => {
    const jump = rawFix(44.53, 132.83, 12, baseTs + 2000, 0);
    expect(isOutlier(jump, previous)).toBe(true);
  });

  it('accepts movement after enough time elapsed', () => {
    const moved = rawFix(44.53, 132.83, 12, baseTs + 10_000, 0);
    expect(isOutlier(moved, previous)).toBe(false);
  });
});

describe('smoothFix', () => {
  it('returns first fix without smoothing', () => {
    const fix = rawFix(44.529392, 132.828296, 15);
    const result = smoothFix(fix, null);
    expect(result).toEqual({
      lat: 44.529392,
      lon: 132.828296,
      accuracy: 15,
      timestamp: baseTs,
      source: 'raw',
    });
  });

  it('smooths two nearby fixes', () => {
    const first = smoothFix(rawFix(44.529392, 132.828296, 20), null)!;
    const second = smoothFix(rawFix(44.5294, 132.8283, 10, baseTs + 1000), first)!;
    expect(second.source).toBe('smoothed');
    expect(second.lat).toBeGreaterThan(44.529392);
    expect(second.lat).toBeLessThan(44.5294);
  });

  it('ignores very poor accuracy fixes', () => {
    const poor = rawFix(44.529392, 132.828296, 120);
    expect(smoothFix(poor, null)).toBeNull();
  });
});

describe('processFix stationary averaging', () => {
  it('averages fixes after standing still for 5 seconds', () => {
    let state = createGeoFilterState();
    const fixes = [
      rawFix(44.52939, 132.82829, 12, baseTs, 0),
      rawFix(44.52940, 132.82830, 10, baseTs + 2000, 0),
      rawFix(44.52941, 132.82831, 8, baseTs + 4000, 0),
      rawFix(44.52942, 132.82832, 8, baseTs + 6000, 0),
    ];

    let last = null as ReturnType<typeof processFix>['result'];
    for (const fix of fixes) {
      const out = processFix(fix, state);
      state = out.state;
      if (out.result) last = out.result;
    }

    expect(last).not.toBeNull();
    expect(last!.lat).toBeGreaterThan(44.52939);
    expect(last!.lat).toBeLessThan(44.52943);
    expect(last!.source).toBe('smoothed');
  });
});
