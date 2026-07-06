import { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchStatus, type StatusData } from '../api/client';
import EngineerChatSheet, { EngineerChatAside } from '../components/EngineerChatSheet';
import EngineerOrderBanner from '../components/EngineerOrderBanner';
import EngineerRadioBadge from '../components/EngineerRadioBadge';
import EngineerTargetPopup from '../components/EngineerTargetPopup';
import Stage1PhaseBanner from '../components/Stage1PhaseBanner';
import GameMap from '../components/GameMap';
import LogoutButton from '../components/LogoutButton';
import { useEngineerLocationPing } from '../hooks/useEngineerLocationPing';
import { useEngineerOrders } from '../context/EngineerOrdersContext';
import { useGeolocation } from '../hooks/useGeolocation';
import { useWakeLock } from '../hooks/useWakeLock';
import GpsStatusIndicator from '../components/GpsStatusIndicator';
import { applyGpsOffset } from '../utils/gpsOffset';
import 'leaflet/dist/leaflet.css';

type MapSelection = { kind: 'point' | 'cache'; id: number };

export default function EngineerPage() {
  const navigate = useNavigate();
  const side = (localStorage.getItem('side') || 'A') as 'A' | 'B';
  const username = localStorage.getItem('username') || '';
  const { latest } = useEngineerOrders();

  const [mapOpen, setMapOpen] = useState(true);
  const [chatOpen, setChatOpen] = useState(false);
  const [data, setData] = useState<StatusData | null>(null);
  const [mapSelection, setMapSelection] = useState<MapSelection | null>(null);
  const [flyTo, setFlyTo] = useState<[number, number] | null>(null);
  const [flyToKey, setFlyToKey] = useState(0);

  useWakeLock(true);
  const { position: rawPosition, gpsStatus, error: geoError, refresh } = useGeolocation();
  const position = useMemo(
    () => applyGpsOffset(rawPosition, data?.gps_lat_offset ?? 0, data?.gps_lon_offset ?? 0),
    [rawPosition, data?.gps_lat_offset, data?.gps_lon_offset],
  );
  useEngineerLocationPing(position);

  const loadStatus = useCallback(() => {
    fetchStatus().then(setData).catch(() => {});
  }, []);

  useEffect(() => {
    if (!mapOpen) return;
    loadStatus();
    const id = setInterval(loadStatus, 15000);
    return () => clearInterval(id);
  }, [mapOpen, loadStatus]);

  useEffect(() => {
    if (!mapOpen || !flyTo) return;
    setFlyToKey((n) => n + 1);
  }, [mapOpen, flyTo]);

  const focusTarget = useCallback((kind: 'point' | 'cache', id: number, lat: number, lon: number) => {
    setMapOpen(true);
    setMapSelection({ kind, id });
    setFlyTo([lat, lon]);
    setFlyToKey((n) => n + 1);
  }, []);

  useEffect(() => {
    if (!latest) return;
    focusTarget(latest.target_kind, latest.target_id, latest.target_lat, latest.target_lon);
  }, [latest?.id, focusTarget, latest]);

  const handleShowOrderOnMap = useCallback(() => {
    if (!latest) return;
    focusTarget(latest.target_kind, latest.target_id, latest.target_lat, latest.target_lon);
  }, [latest, focusTarget]);

  const sideLabel = side === 'A' ? 'ЛК' : 'СБГ';
  const sideColor = side === 'A' ? 'text-sideA' : 'text-sideB';

  const defaultCenter: [number, number] | undefined = position
    ? [position.lat, position.lon]
    : undefined;

  const orderMatchesSelection =
    latest &&
    mapSelection &&
    latest.target_kind === mapSelection.kind &&
    latest.target_id === mapSelection.id;

  return (
    <div className="h-dvh flex flex-col overflow-hidden bg-bg">
      <header className="shrink-0 p-4 border-b border-zinc-800 flex justify-between items-start gap-3">
        <div className="min-w-0">
          <h1 className={`font-bold text-lg ${sideColor}`}>Инженер · {sideLabel}</h1>
          <p className="text-sm text-zinc-400 font-mono truncate">{username}</p>
          <div className="mt-1">
            <GpsStatusIndicator
              gpsStatus={gpsStatus}
              accuracy={position?.accuracy ?? null}
              error={geoError}
              onRefresh={refresh}
            />
          </div>
          <div className="mt-2 space-y-2">
            <EngineerRadioBadge />
            {data && <Stage1PhaseBanner data={data} />}
            <EngineerOrderBanner onShowOnMap={handleShowOrderOnMap} />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <button
            type="button"
            className={`btn text-sm border min-h-0 py-1.5 px-3 ${
              mapOpen ? 'border-sideA bg-sideA/15 text-sideA' : 'border-zinc-600 text-zinc-300'
            }`}
            onClick={() => setMapOpen(!mapOpen)}
          >
            Карта {mapOpen ? '▼' : '▲'}
          </button>
          <EngineerChatSheet side={side} variant="toggle" open={chatOpen} onOpenChange={setChatOpen} />
          <LogoutButton />
        </div>
      </header>

      {mapOpen ? (
        <div className="flex-1 flex flex-col md:flex-row min-h-0 min-h-[50vh]">
          <div className="map-page flex-1 min-h-[40vh] md:min-h-0 relative">
            {data ? (
              <GameMap
                data={data}
                center={defaultCenter}
                zoom={14}
                autoFitBounds={false}
                flyTo={flyTo}
                flyToKey={flyToKey}
                flyToZoom={17}
                userPosition={position}
                showRadii
                viewerSide={side}
                pulsePointId={
                  latest?.target_kind === 'point'
                    ? latest.target_id
                    : mapSelection?.kind === 'point'
                      ? mapSelection.id
                      : null
                }
                pulseCacheId={
                  latest?.target_kind === 'cache'
                    ? latest.target_id
                    : mapSelection?.kind === 'cache'
                      ? mapSelection.id
                      : null
                }
                adminSelection={mapSelection}
                onAdminPopupClose={() => setMapSelection(null)}
                renderAdminPopup={({ kind, data: target }) => (
                  <EngineerTargetPopup
                    kind={kind}
                    data={target}
                    orderNote={orderMatchesSelection ? latest?.note : null}
                    stage1Phase={data.stage1_phase}
                    side={side}
                    onClose={() => setMapSelection(null)}
                    onOpenCapture={() => navigate(`/point/${target.id}`)}
                  />
                )}
                onPointClick={(p) => focusTarget('point', p.id, p.lat, p.lon)}
                onCacheClick={(c) => focusTarget('cache', c.id, c.lat, c.lon)}
              />
            ) : (
              <div className="absolute inset-0 flex items-center justify-center text-zinc-500 text-sm">
                Загрузка карты…
              </div>
            )}
          </div>
          {chatOpen && (
            <EngineerChatAside
              side={side}
              onClose={() => setChatOpen(false)}
              className="shrink-0 h-[min(45vh,400px)] md:h-auto md:w-[min(100%,22rem)] border-t md:border-t-0 md:border-l"
            />
          )}
        </div>
      ) : chatOpen ? (
        <EngineerChatAside side={side} onClose={() => setChatOpen(false)} className="flex-1 min-h-0" />
      ) : (
        <main className="flex-1 flex flex-col items-center justify-center p-6 text-center">
          <p className="text-lg text-zinc-300">Карта скрыта</p>
          <p className="text-sm text-zinc-500 mt-2">Нажмите «Карта ▲» — тап по точке откроет попап на карте</p>
          {position && (
            <p className="text-[11px] text-zinc-600 font-mono mt-4">
              GPS {position.lat.toFixed(5)}, {position.lon.toFixed(5)}
            </p>
          )}
        </main>
      )}
    </div>
  );
}
