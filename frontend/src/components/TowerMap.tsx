import { MapContainer, Marker, Tooltip, TileLayer } from 'react-leaflet';
import L from 'leaflet';
import 'leaflet/dist/leaflet.css';
import { TOWER_MAP_CENTER, type TowerMapPoint } from '../data/towerMapPoints';

const KIND_COLOR: Record<string, string> = {
  village: '#22C55E',
  kpp: '#F59E0B',
  gate: '#3B82F6',
  mine: '#EF4444',
  default: '#94A3B8',
};

function kindOf(name: string): string {
  if (name.startsWith('Деревня')) return 'village';
  if (name.startsWith('КПП')) return 'kpp';
  if (/^Г\d/.test(name)) return 'gate';
  if (name.startsWith('Шахта')) return 'mine';
  return 'default';
}

function pointIcon(name: string, clickable: boolean) {
  const color = KIND_COLOR[kindOf(name)];
  const ring = clickable ? '<circle cx="10" cy="10" r="9" fill="none" stroke="#fff" stroke-width="1.5" stroke-dasharray="2 2"/>' : '';
  return L.divIcon({
    className: '',
    html: `<svg width="20" height="20" viewBox="0 0 20 20">${ring}<circle cx="10" cy="10" r="7" fill="${color}" stroke="#0B0F19" stroke-width="2"/></svg>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

const FACTION_COLOR: Record<string, string> = {
  sbg: '#3B82F6',
  drg: '#EF4444',
  prvonek: '#F5F5F4',
  korbul: '#18181B',
};

function personIcon(factionCode: string) {
  const color = FACTION_COLOR[factionCode] || '#A855F7';
  const stroke = factionCode === 'korbul' ? '#F5F5F4' : '#0B0F19';
  return L.divIcon({
    className: '',
    html: `<svg width="22" height="22" viewBox="0 0 22 22"><circle cx="11" cy="11" r="8" fill="${color}" stroke="${stroke}" stroke-width="2"/><circle cx="11" cy="11" r="2.5" fill="${stroke}"/></svg>`,
    iconSize: [22, 22],
    iconAnchor: [11, 11],
  });
}

export interface TowerRosterMarker {
  username: string;
  faction_code: string;
  faction_name: string;
  lat: number;
  lon: number;
  updated_at: string;
}

export default function TowerMap({
  points,
  height = '260px',
  clickableNames,
  onMarkerClick,
  roster,
}: {
  points: TowerMapPoint[];
  height?: string;
  clickableNames?: Set<string>;
  onMarkerClick?: (name: string) => void;
  roster?: TowerRosterMarker[];
}) {
  return (
    <div className="rounded-lg overflow-hidden border border-zinc-800" style={{ height }}>
      <MapContainer center={TOWER_MAP_CENTER} zoom={15} className="w-full h-full" attributionControl={false}>
        <TileLayer url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}" />
        {points.map((p) => {
          const clickable = clickableNames?.has(p.name) ?? false;
          return (
            <Marker
              key={p.name}
              position={[p.lat, p.lon]}
              icon={pointIcon(p.name, clickable)}
              eventHandlers={clickable && onMarkerClick ? { click: () => onMarkerClick(p.name) } : undefined}
            >
              <Tooltip direction="top" offset={[0, -10]} permanent={false}>
                {p.name}
                {clickable ? ' · тест-скан' : ''}
              </Tooltip>
            </Marker>
          );
        })}
        {roster?.map((r) => (
          <Marker key={`u-${r.username}`} position={[r.lat, r.lon]} icon={personIcon(r.faction_code)} zIndexOffset={1000}>
            <Tooltip direction="top" offset={[0, -12]} permanent={false}>
              {r.username} · {r.faction_name} · {new Date(r.updated_at).toLocaleTimeString()}
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
