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

function pointIcon(name: string) {
  const color = KIND_COLOR[kindOf(name)];
  return L.divIcon({
    className: '',
    html: `<svg width="20" height="20" viewBox="0 0 20 20"><circle cx="10" cy="10" r="7" fill="${color}" stroke="#0B0F19" stroke-width="2"/></svg>`,
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });
}

export default function TowerMap({
  points,
  height = '260px',
}: {
  points: TowerMapPoint[];
  height?: string;
}) {
  return (
    <div className="rounded-lg overflow-hidden border border-zinc-800" style={{ height }}>
      <MapContainer center={TOWER_MAP_CENTER} zoom={15} className="w-full h-full" attributionControl={false}>
        <TileLayer url="https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}" />
        {points.map((p) => (
          <Marker key={p.name} position={[p.lat, p.lon]} icon={pointIcon(p.name)}>
            <Tooltip direction="top" offset={[0, -10]} permanent={false}>
              {p.name}
            </Tooltip>
          </Marker>
        ))}
      </MapContainer>
    </div>
  );
}
