import { useEffect, useState } from 'react';
import { fetchMapGrid, type MapGridData } from '../api/client';

export function useMapGrid() {
  const [grid, setGrid] = useState<MapGridData | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetchMapGrid()
      .then((data) => {
        if (!cancelled) setGrid(data);
      })
      .catch(() => {
        if (!cancelled) setGrid(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  return grid;
}
