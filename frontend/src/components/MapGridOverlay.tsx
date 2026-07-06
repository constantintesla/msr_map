import { ImageOverlay } from 'react-leaflet';
import type { MapGridData } from '../api/client';

interface MapGridOverlayProps {
  grid: MapGridData;
  opacity?: number;
}

export default function MapGridOverlay({ grid, opacity = 0.9 }: MapGridOverlayProps) {
  const imageUrl = grid.image_url.startsWith('http')
    ? grid.image_url
    : `${import.meta.env.VITE_API_URL || ''}${grid.image_url}`;

  return (
    <ImageOverlay
      url={imageUrl}
      bounds={[
        [grid.south, grid.west],
        [grid.north, grid.east],
      ]}
      opacity={opacity}
      zIndex={150}
    />
  );
}
