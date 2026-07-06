import { MapContainer, Marker, Popup, TileLayer, Circle, Tooltip, useMap, useMapEvents } from 'react-leaflet';
import L from 'leaflet';
import { useEffect, useRef } from 'react';
import type { ReactNode } from 'react';
import type { StatusData, EngineerLocation } from '../api/client';

import { FENCE_RADIUS_M } from '../utils/haversine';
import { pointController } from '../utils/pointControl';
import MapGridOverlay from './MapGridOverlay';
import { useMapGrid } from '../hooks/useMapGrid';

const SIDE_A = '#3B82F6';
const SIDE_B = '#EF4444';

const ENGINEER_COLORS = ['#06B6D4', '#A78BFA', '#F472B6', '#34D399', '#FB923C', '#E879F9', '#2DD4BF', '#FACC15'];

function engineerColor(username: string): string {
  let h = 0;
  for (let i = 0; i < username.length; i++) h = (h * 31 + username.charCodeAt(i)) >>> 0;
  return ENGINEER_COLORS[h % ENGINEER_COLORS.length];
}

function engineerIcon(color: string) {
  return L.divIcon({
    className: '',
    html: `<svg width="26" height="34" viewBox="0 0 26 34">
      <path d="M13 0 C6 0 1 5.5 1 12.5 C1 23 13 34 13 34 C13 34 25 23 25 12.5 C25 5.5 20 0 13 0 Z" fill="${color}" stroke="#E2E8F0" stroke-width="1.5"/>
      <circle cx="13" cy="12" r="4.5" fill="#0f172a" opacity="0.35"/>
      <circle cx="13" cy="12" r="2.5" fill="#fff"/>
    </svg>`,
    iconSize: [26, 34],
    iconAnchor: [13, 34],
  });
}

const pointIcon = (
  side: string | null,
  heldBy: string | null,
  warn: boolean,
  destroyed?: boolean,
  pendingAdmin?: boolean,
  adminConfirmed?: boolean,
  stage1Muted?: boolean
) => {
  if (destroyed) {
    const stroke = pendingAdmin ? '#F59E0B' : adminConfirmed ? '#6B7280' : '#EF4444';
    return L.divIcon({
      className: '',
      html: `<svg width="28" height="28" viewBox="0 0 28 28"><text x="14" y="20" text-anchor="middle" fill="${stroke}" font-size="20" font-weight="bold">✕</text></svg>`,
      iconSize: [28, 28],
      iconAnchor: [14, 14],
    });
  }
  const fill = stage1Muted
    ? '#4B5563'
    : warn
      ? '#F59E0B'
      : heldBy === 'A'
        ? SIDE_A
        : heldBy === 'B'
          ? SIDE_B
          : side === 'A'
            ? SIDE_A
            : side === 'B'
              ? SIDE_B
              : '#64748B';
  const pulse = warn && !stage1Muted ? 'class="marker-pulse"' : '';
  return L.divIcon({
    className: '',
    html: `<svg width="28" height="28" viewBox="0 0 28 28" ${pulse}><circle cx="14" cy="14" r="11" fill="${fill}" stroke="#E2E8F0" stroke-width="2"/></svg>`,
    iconSize: [28, 28],
    iconAnchor: [14, 14],
  });
};

const cacheIcon = (
  destroyed: boolean,
  teamSide: string | null,
  cacheKind: string,
  delivered: boolean,
  pendingAdmin?: boolean,
  adminConfirmed?: boolean,
  viewerSide?: string | null,
  destroyedBySide?: string | null,
  deliveredBySide?: string | null,
  stage2Muted?: boolean
) => {
  if (cacheKind === 'film_loot') {
    if (stage2Muted) {
      const fill = '#4B5563';
      const stroke = '#6B7280';
      return L.divIcon({
        className: '',
        html: `<svg width="28" height="28" viewBox="0 0 28 28">
        <rect x="4" y="10" width="20" height="14" rx="2" fill="${fill}" stroke="${stroke}" stroke-width="1.5"/>
        <path d="M4 12 Q14 8 24 12" fill="none" stroke="#9CA3AF" stroke-width="1.5" opacity="0.7"/>
      </svg>`,
        iconSize: [28, 28],
        iconAnchor: [14, 20],
      });
    }
    if (delivered) {
      const color =
        deliveredBySide === 'A' ? SIDE_A : deliveredBySide === 'B' ? SIDE_B : '#22C55E';
      return L.divIcon({
        className: '',
        html: `<svg width="26" height="26"><rect x="3" y="8" width="20" height="14" rx="2" fill="#374151" stroke="${color}" stroke-width="2"/><text x="13" y="19" text-anchor="middle" fill="${color}" font-size="10">✓</text></svg>`,
        iconSize: [26, 26],
        iconAnchor: [13, 18],
      });
    }
    if (destroyed) {
      const fill =
        destroyedBySide === 'A' ? SIDE_A : destroyedBySide === 'B' ? SIDE_B : '#A855F7';
      return L.divIcon({
        className: '',
        html: `<svg width="28" height="28" viewBox="0 0 28 28">
        <rect x="4" y="10" width="20" height="14" rx="2" fill="${fill}" stroke="#E2E8F0" stroke-width="1.5"/>
        <path d="M4 12 Q14 8 24 12" fill="none" stroke="#93C5FD" stroke-width="2" opacity="0.9"/>
      </svg>`,
        iconSize: [28, 28],
        iconAnchor: [14, 20],
      });
    }
    const fill = '#F59E0B';
    return L.divIcon({
      className: '',
      html: `<svg width="28" height="28" viewBox="0 0 28 28">
        <rect x="4" y="10" width="20" height="14" rx="2" fill="${fill}" stroke="#E2E8F0" stroke-width="1.5"/>
        <path d="M4 12 Q14 8 24 12" fill="none" stroke="#93C5FD" stroke-width="2" opacity="0.9"/>
      </svg>`,
      iconSize: [28, 28],
      iconAnchor: [14, 20],
    });
  }
  const fill = destroyed ? '#374151' : teamSide === 'A' ? SIDE_A : teamSide === 'B' ? SIDE_B : '#F59E0B';
  if (destroyed) {
    const stroke = pendingAdmin ? '#F59E0B' : adminConfirmed ? '#6B7280' : '#EF4444';
    return L.divIcon({
      className: '',
      html: `<svg width="24" height="24" viewBox="0 0 24 24"><text x="12" y="17" text-anchor="middle" fill="${stroke}" font-size="18" font-weight="bold">✕</text></svg>`,
      iconSize: [24, 24],
      iconAnchor: [12, 18],
    });
  }
  return L.divIcon({
    className: '',
    html: `<svg width="22" height="22" viewBox="0 0 22 22"><rect x="2" y="6" width="18" height="13" rx="2" fill="${fill}" stroke="#E2E8F0" stroke-width="1.5"/></svg>`,
    iconSize: [22, 22],
    iconAnchor: [11, 17],
  });
};

/** Базы, старты и комбинированные метки из Задача1.kml */
const landmarkIcon = (kind: string, teamSide: string) => {
  const color = teamSide === 'A' ? SIDE_A : SIDE_B;
  const stroke = '#E2E8F0';

  if (kind === 'base_start') {
    return L.divIcon({
      className: '',
      html: `<svg width="40" height="40" viewBox="0 0 40 40">
        <circle cx="20" cy="20" r="18" fill="#000" fill-opacity="0.55" stroke="${color}" stroke-width="2.5"/>
        <path d="M12 26 L20 14 L28 26 Z" fill="${color}" stroke="${stroke}" stroke-width="1.2"/>
        <rect x="16" y="24" width="8" height="8" fill="${color}" stroke="${stroke}" stroke-width="1"/>
        <line x1="20" y1="10" x2="20" y2="14" stroke="${color}" stroke-width="2"/>
      </svg>`,
      iconSize: [40, 40],
      iconAnchor: [20, 20],
    });
  }

  if (kind === 'base') {
    return L.divIcon({
      className: '',
      html: `<svg width="36" height="36" viewBox="0 0 36 36">
        <circle cx="18" cy="18" r="16" fill="#000" fill-opacity="0.5" stroke="${color}" stroke-width="2.5"/>
        <path d="M10 24 L18 12 L26 24 Z" fill="${color}" stroke="${stroke}" stroke-width="1.5"/>
        <rect x="14" y="22" width="8" height="8" fill="${color}" stroke="${stroke}" stroke-width="1"/>
      </svg>`,
      iconSize: [36, 36],
      iconAnchor: [18, 18],
    });
  }

  // start
  return L.divIcon({
    className: '',
    html: `<svg width="34" height="34" viewBox="0 0 34 34">
      <circle cx="17" cy="17" r="15" fill="#000" fill-opacity="0.5" stroke="${color}" stroke-width="2" stroke-dasharray="4 3"/>
      <line x1="17" y1="8" x2="17" y2="26" stroke="${color}" stroke-width="2.5"/>
      <path d="M17 8 L26 13 L17 18 Z" fill="${color}" stroke="${stroke}" stroke-width="1"/>
    </svg>`,
    iconSize: [34, 34],
    iconAnchor: [17, 17],
  });
};

function FitBounds({
  data,
  engineers,
  grid,
  enabled = true,
}: {
  data: StatusData;
  engineers?: EngineerLocation[];
  grid?: { north: number; south: number; east: number; west: number } | null;
  enabled?: boolean;
}) {
  const map = useMap();
  const didFit = useRef(false);
  useEffect(() => {
    if (!enabled) return;
    if (didFit.current) return;
    const coords: [number, number][] = [
      ...data.points.map((p) => [p.lat, p.lon] as [number, number]),
      ...data.caches.map((c) => [c.lat, c.lon] as [number, number]),
      ...(data.landmarks || []).map((lm) => [lm.lat, lm.lon] as [number, number]),
      ...(engineers || []).map((e) => [e.lat, e.lon] as [number, number]),
    ];
    if (grid) {
      coords.push(
        [grid.north, grid.west],
        [grid.north, grid.east],
        [grid.south, grid.west],
        [grid.south, grid.east],
      );
    }
    if (!coords.length) return;
    didFit.current = true;
    map.fitBounds(coords, { padding: [48, 48], maxZoom: 16 });
  }, [data, engineers, grid, map, enabled]);
  return null;
}

function MapResize() {
  const map = useMap();
  useEffect(() => {
    const fix = () => map.invalidateSize();
    fix();
    const t1 = setTimeout(fix, 100);
    const t2 = setTimeout(fix, 500);
    window.addEventListener('resize', fix);
    return () => {
      clearTimeout(t1);
      clearTimeout(t2);
      window.removeEventListener('resize', fix);
    };
  }, [map]);
  return null;
}

function FlyTo({ center, zoom, flyKey }: { center?: [number, number]; zoom?: number; flyKey?: number }) {
  const map = useMap();
  const lastKey = useRef('');
  useEffect(() => {
    if (!center) return;
    const key = `${center[0]},${center[1]},${zoom ?? 16},${flyKey ?? 0}`;
    if (key === lastKey.current) return;
    lastKey.current = key;

    const run = () => {
      map.invalidateSize({ animate: false });
      map.flyTo(center, zoom ?? 16, { duration: 0.65 });
    };
    const t = setTimeout(run, 80);
    return () => clearTimeout(t);
  }, [center, zoom, flyKey, map]);
  return null;
}

const orderPulseIcon = L.divIcon({
  className: 'order-pulse-icon',
  html: '<div class="order-pulse-ring"></div>',
  iconSize: [52, 52],
  iconAnchor: [26, 26],
});

function OrderPulseMarker({ lat, lon }: { lat: number; lon: number }) {
  return (
    <Marker
      position={[lat, lon]}
      icon={orderPulseIcon}
      interactive={false}
      zIndexOffset={250}
    />
  );
}

function MapClickHandler({ enabled, onClick }: { enabled: boolean; onClick: (lat: number, lon: number) => void }) {
  useMapEvents({
    click(e) {
      if (!enabled) return;
      onClick(e.latlng.lat, e.latlng.lng);
    },
  });
  return null;
}

type AdminSelection = { kind: 'point' | 'cache' | 'landmark'; id: number };

export type MapCreateTarget =
  | { kind: 'point'; stage: 1 | 3 }
  | {
      kind: 'cache';
      stage: 2 | 3;
      cache_kind: 'film_loot' | 'post' | 'mertvyak';
      team_side?: 'A' | 'B';
    }
  | { kind: 'landmark'; landmarkKind: 'base' | 'start' | 'base_start'; team_side: 'A' | 'B' };

type AdminPopupRenderer = (target: {
  kind: 'point' | 'cache' | 'landmark';
  data:
    | StatusData['points'][number]
    | StatusData['caches'][number]
    | NonNullable<StatusData['landmarks']>[number];
}) => ReactNode;

interface GameMapProps {
  data: StatusData;
  center?: [number, number];
  zoom?: number;
  showFence?: { lat: number; lon: number; radius?: number };
  userPosition?: { lat: number; lon: number; accuracy?: number } | null;
  pulsePointId?: number | null;
  pulseCacheId?: number | null;
  warnPointId?: number | null;
  explosionCacheId?: number | null;
  showRadii?: boolean;
  flyTo?: [number, number] | null;
  flyToKey?: number;
  flyToZoom?: number;
  autoFitBounds?: boolean;
  adminSelection?: AdminSelection | null;
  renderAdminPopup?: AdminPopupRenderer;
  onCacheClick?: (cache: StatusData['caches'][number]) => void;
  onPointClick?: (point: StatusData['points'][number]) => void;
  onAdminPopupClose?: () => void;
  engineers?: EngineerLocation[];
  viewerSide?: string | null;
  adminStage2Overview?: boolean;
  showGrid?: boolean;
  mapEditMode?: boolean;
  createTarget?: MapCreateTarget | null;
  onObjectMove?: (kind: 'point' | 'cache' | 'landmark', id: number, lat: number, lon: number) => void;
  onMapClickCreate?: (lat: number, lon: number) => void;
  onLandmarkClick?: (landmark: NonNullable<StatusData['landmarks']>[number]) => void;
}

const hiddenPopupIcon = L.divIcon({
  className: 'leaflet-admin-popup-anchor',
  html: '',
  iconSize: [1, 1],
  iconAnchor: [0, 0],
});

function AdminSelectionPopup({
  adminSelection,
  data,
  renderAdminPopup,
  onClose,
}: {
  adminSelection: AdminSelection;
  data: StatusData;
  renderAdminPopup: AdminPopupRenderer;
  onClose?: () => void;
}) {
  const markerRef = useRef<L.Marker>(null);

  const target =
    adminSelection.kind === 'point'
      ? data.points.find((p) => p.id === adminSelection.id)
      : adminSelection.kind === 'cache'
        ? data.caches.find((c) => c.id === adminSelection.id)
        : (data.landmarks || []).find((lm) => lm.id === adminSelection.id);

  const content = target
    ? renderAdminPopup({
        kind: adminSelection.kind,
        data: target as StatusData['points'][number] &
          StatusData['caches'][number] &
          NonNullable<StatusData['landmarks']>[number],
      })
    : null;

  useEffect(() => {
    if (!target) return;
    const timer = window.setTimeout(() => markerRef.current?.openPopup(), 0);
    return () => window.clearTimeout(timer);
  }, [adminSelection.kind, adminSelection.id, target?.lat, target?.lon]);

  if (!target || !content) return null;

  return (
    <Marker
      ref={markerRef}
      position={[target.lat, target.lon]}
      icon={hiddenPopupIcon}
      interactive={false}
      zIndexOffset={2000}
    >
      <Popup
        className="admin-map-popup"
        maxWidth={340}
        minWidth={260}
        autoClose={false}
        closeOnClick={false}
        eventHandlers={{
          popupclose: () => onClose?.(),
        }}
      >
        {content}
      </Popup>
    </Marker>
  );
}

export default function GameMap({
  data,
  center,
  zoom = 14,
  showFence,
  userPosition,
  pulsePointId,
  pulseCacheId,
  warnPointId,
  explosionCacheId,
  showRadii = false,
  flyTo,
  flyToKey,
  flyToZoom = 16,
  autoFitBounds = true,
  adminSelection,
  renderAdminPopup,
  onCacheClick,
  onPointClick,
  onAdminPopupClose,
  engineers = [],
  viewerSide = null,
  adminStage2Overview = false,
  showGrid = true,
  mapEditMode = false,
  createTarget = null,
  onObjectMove,
  onMapClickCreate,
  onLandmarkClick,
}: GameMapProps) {
  const mapGrid = useMapGrid();
  const landmarks = data.landmarks || [];
  const fenceRadius = data.capture_radius_m ?? FENCE_RADIUS_M;
  const defaultCenter: [number, number] = center || [
    landmarks[0]?.lat ?? data.points[0]?.lat ?? 44.52,
    landmarks[0]?.lon ?? data.points[0]?.lon ?? 132.82,
  ];

  const landmarkLabel = (kind: string) => {
    if (kind === 'base_start') return 'База + старт';
    if (kind === 'base') return 'База';
    return 'Старт';
  };

  return (
    <div
      className={`map-root${onPointClick || onCacheClick || onLandmarkClick ? ' map-targets-clickable' : ''}${mapEditMode ? ' map-edit-mode' : ''}${createTarget ? ' map-create-mode' : ''}`}
    >
      <MapContainer
        center={defaultCenter}
        zoom={zoom}
        style={{ height: '100%', width: '100%' }}
        zoomControl={false}
        attributionControl={false}
      >
        <TileLayer
          url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}"
          attribution=""
          maxZoom={20}
        />
        {showGrid && mapGrid && <MapGridOverlay grid={mapGrid} />}
        <MapResize />
        {createTarget && onMapClickCreate && (
          <MapClickHandler enabled onClick={onMapClickCreate} />
        )}
        <FitBounds data={data} engineers={engineers} grid={mapGrid} enabled={autoFitBounds && !flyTo} />
        {flyTo && <FlyTo center={flyTo} zoom={flyToZoom} flyKey={flyToKey} />}

        {/* Базы и старты — рисуем под КТ, но над тайлами */}
        {landmarks.map((lm) => {
          const color = lm.team_side === 'A' ? SIDE_A : SIDE_B;
          const radius = lm.kind === 'start' ? 22 : 28;
          const selected = adminSelection?.kind === 'landmark' && adminSelection.id === lm.id;
          return (
            <Marker
              key={`lm-${lm.id}`}
              position={[lm.lat, lm.lon]}
              icon={landmarkIcon(lm.kind, lm.team_side)}
              zIndexOffset={selected ? 450 : 500}
              draggable={mapEditMode}
              eventHandlers={{
                ...(onLandmarkClick ? { click: () => onLandmarkClick(lm) } : {}),
                ...(mapEditMode && onObjectMove
                  ? {
                      dragend: (e) => {
                        const pos = e.target.getLatLng();
                        onObjectMove('landmark', lm.id, pos.lat, pos.lng);
                      },
                    }
                  : {}),
              }}
            >
              <Circle
                center={[lm.lat, lm.lon]}
                radius={radius}
                pathOptions={{
                  color,
                  fillColor: color,
                  fillOpacity: lm.kind === 'start' ? 0.08 : 0.15,
                  weight: lm.kind === 'start' ? 2 : 3,
                  dashArray: lm.kind === 'start' ? '6 4' : undefined,
                }}
              />
              <Tooltip direction="top" offset={[0, -20]} opacity={0.95}>
                <span style={{ color }}>
                  {landmarkLabel(lm.kind)} {lm.team_side === 'A' ? 'ЛК' : 'СБГ'}
                </span>
                <br />
                <span style={{ fontSize: '11px' }}>{lm.name}</span>
              </Tooltip>
            </Marker>
          );
        })}

        {showRadii &&
          data.points.map((p) => {
            const controller = pointController(p);
            return (
            <Circle
              key={`fence-p-${p.id}`}
              center={[p.lat, p.lon]}
              radius={fenceRadius}
              interactive={false}
              pathOptions={{
                color: controller === 'A' ? SIDE_A : controller === 'B' ? SIDE_B : '#64748B',
                fillColor: controller === 'A' ? SIDE_A : controller === 'B' ? SIDE_B : '#64748B',
                fillOpacity: 0.12,
                weight: 2,
              }}
            />
          );
          })}

        {showRadii &&
          data.caches.map((c) => (
            <Circle
              key={`fence-c-${c.id}`}
              center={[c.lat, c.lon]}
              radius={fenceRadius}
              interactive={false}
              pathOptions={{
                color: c.destroyed ? '#374151' : c.team_side === 'A' ? SIDE_A : c.team_side === 'B' ? SIDE_B : '#F59E0B',
                fillColor: c.destroyed ? '#374151' : c.team_side === 'A' ? SIDE_A : c.team_side === 'B' ? SIDE_B : '#F59E0B',
                fillOpacity: c.destroyed ? 0.05 : 0.1,
                weight: 1,
                dashArray: c.destroyed ? '4 4' : undefined,
              }}
            />
          ))}

        {data.points.map((p) => {
          const selected = adminSelection?.kind === 'point' && adminSelection.id === p.id;
          const controller = pointController(p);
          const stage1ScheduleActive = data.current_stage !== 3;
          const stage1Muted =
            stage1ScheduleActive &&
            data.stage1_phase === 'hold' &&
            !p.stage1_capturable &&
            !p.side &&
            !p.held_by;
          const stage1Tooltip = stage1Muted ? ' · не в слоте' : '';
          return (
            <Marker
              key={`p-${p.id}`}
              position={[p.lat, p.lon]}
              icon={pointIcon(
                p.side,
                controller,
                warnPointId === p.id,
                p.destroyed,
                p.pending_admin,
                p.admin_confirmed,
                stage1Muted
              )}
              zIndexOffset={selected ? 400 : stage1Muted ? 100 : 300}
              draggable={mapEditMode}
              eventHandlers={{
                ...(onPointClick ? { click: () => onPointClick(p) } : {}),
                ...(mapEditMode && onObjectMove
                  ? {
                      dragend: (e) => {
                        const pos = e.target.getLatLng();
                        onObjectMove('point', p.id, pos.lat, pos.lng);
                      },
                    }
                  : {}),
              }}
            >
              <Tooltip direction="top" offset={[0, -14]}>
                {p.name}
                {stage1Tooltip}
                {onPointClick ? ' · нажмите' : ''}
              </Tooltip>
            </Marker>
          );
        })}

        {pulsePointId != null && (() => {
          const p = data.points.find((pt) => pt.id === pulsePointId);
          return p ? <OrderPulseMarker key={`pulse-p-${p.id}`} lat={p.lat} lon={p.lon} /> : null;
        })()}
        {pulseCacheId != null && (() => {
          const c = data.caches.find((ch) => ch.id === pulseCacheId);
          return c ? <OrderPulseMarker key={`pulse-c-${c.id}`} lat={c.lat} lon={c.lon} /> : null;
        })()}

        {data.caches.map((c) => {
          const selected = adminSelection?.kind === 'cache' && adminSelection.id === c.id;
          const stage2LootActive = data.stage2_enabled || data.current_stage === 2;
          const stage2Muted =
            adminStage2Overview &&
            stage2LootActive &&
            c.cache_kind === 'film_loot' &&
            !c.stage2_active;
          return (
            <Marker
              key={`c-${c.id}`}
              position={[c.lat, c.lon]}
              icon={cacheIcon(
                c.destroyed,
                c.team_side,
                c.cache_kind || 'post',
                c.delivered,
                c.pending_admin,
                c.admin_confirmed,
                viewerSide,
                c.destroyed_by_side,
                c.delivered_by_side,
                stage2Muted
              )}
              zIndexOffset={selected ? 350 : 200}
              draggable={mapEditMode}
              eventHandlers={{
                ...(onCacheClick ? { click: () => onCacheClick(c) } : {}),
                ...(mapEditMode && onObjectMove
                  ? {
                      dragend: (e) => {
                        const pos = e.target.getLatLng();
                        onObjectMove('cache', c.id, pos.lat, pos.lng);
                      },
                    }
                  : {}),
              }}
            >
              {explosionCacheId === c.id && (
                <Circle
                  center={[c.lat, c.lon]}
                  radius={40}
                  pathOptions={{ color: '#F59E0B', fillOpacity: 0, className: 'explosion-ring' }}
                />
              )}
              <Tooltip direction="top" offset={[0, -14]}>
                {c.name}
                {onCacheClick ? ' · нажмите' : ''}
              </Tooltip>
            </Marker>
          );
        })}

        {adminSelection && renderAdminPopup && (
          <AdminSelectionPopup
            adminSelection={adminSelection}
            data={data}
            renderAdminPopup={renderAdminPopup}
            onClose={onAdminPopupClose}
          />
        )}

        {showFence && (
          <Circle
            center={[showFence.lat, showFence.lon]}
            radius={showFence.radius ?? fenceRadius}
            pathOptions={{ color: '#F59E0B', fillColor: '#F59E0B', fillOpacity: 0.15, weight: 2 }}
          />
        )}

        {engineers.map((eng) => {
          const color = engineerColor(eng.username);
          return (
            <Marker
              key={`eng-${eng.user_id}`}
              position={[eng.lat, eng.lon]}
              icon={engineerIcon(color)}
              zIndexOffset={900}
            >
              {eng.accuracy > 0 && (
                <Circle
                  center={[eng.lat, eng.lon]}
                  radius={Math.min(eng.accuracy, 80)}
                  pathOptions={{ color, fillColor: color, fillOpacity: 0.12, weight: 1, dashArray: '3 3' }}
                />
              )}
              <Tooltip direction="top" offset={[0, -34]} permanent className="engineer-label-tooltip">
                <span style={{ color, fontWeight: 600, fontSize: '11px' }}>{eng.label}</span>
              </Tooltip>
            </Marker>
          );
        })}

        {userPosition && (
          <>
            {userPosition.accuracy != null && userPosition.accuracy > 0 && (
              <Circle
                center={[userPosition.lat, userPosition.lon]}
                radius={Math.min(userPosition.accuracy, 80)}
                pathOptions={{
                  color: '#22C55E',
                  fillColor: '#22C55E',
                  fillOpacity: 0.15,
                  weight: 1,
                  dashArray: '4 4',
                }}
              />
            )}
            <Marker
              position={[userPosition.lat, userPosition.lon]}
              icon={L.divIcon({
                className: '',
                html: `<svg width="18" height="18"><circle cx="9" cy="9" r="7" fill="#22C55E" stroke="#fff" stroke-width="2"/></svg>`,
                iconSize: [18, 18],
                iconAnchor: [9, 9],
              })}
              zIndexOffset={1000}
            />
          </>
        )}
      </MapContainer>
    </div>
  );
}
