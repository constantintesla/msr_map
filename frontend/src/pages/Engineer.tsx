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
    loadStatus();
    const id = setInterval(loadStatus, 15000);
    return () => clearInterval(id);
  }, [loadStatus]);

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

  const actionBtnClass =
    'btn text-[11px] md:text-sm border min-h-0 py-1 px-2 md:py-1.5 md:px-3 rounded-md';

  const toggleMap = useCallback(() => {
    setMapOpen((wasOpen) => {
      if (wasOpen) setChatOpen(true);
      return !wasOpen;
    });
  }, []);

  const handleChatOpenChange = useCallback((open: boolean) => {
    if (!open) setMapOpen((mapWasOpen) => mapWasOpen || true);
    setChatOpen(open);
  }, []);

  useEffect(() => {
    if (!mapOpen && !chatOpen) {
      setMapOpen(true);
    }
  }, [mapOpen, chatOpen]);

  return (
    <div className="h-dvh flex flex-col overflow-hidden bg-bg">
      <header className="shrink-0 px-3 py-2 md:p-4 border-b border-zinc-800">
        <div className="min-w-0">
          <h1 className={`font-bold text-base md:text-lg leading-tight ${sideColor}`}>
            Инженер · {sideLabel}
          </h1>
          <div className="mt-0.5 flex items-center gap-1 min-w-0 overflow-x-auto text-[10px] md:text-xs text-zinc-400 font-mono tabular-nums whitespace-nowrap [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
            <span className="truncate max-w-[5.5rem] sm:max-w-[8rem] md:max-w-none text-zinc-300">
              {username}
            </span>
            <span className="text-zinc-700 shrink-0" aria-hidden>
              ·
            </span>
            <EngineerRadioBadge />
            <span className="text-zinc-700 shrink-0" aria-hidden>
              ·
            </span>
            <GpsStatusIndicator
              variant="compact"
              gpsStatus={gpsStatus}
              accuracy={position?.accuracy ?? null}
              onRefresh={refresh}
            />
          </div>
          {(geoError || gpsStatus === 'acquiring' || gpsStatus === 'weak') && (
            <p className="mt-0.5 text-[10px] text-zinc-600 truncate">
              {geoError ??
                (gpsStatus === 'acquiring'
                  ? 'Поиск спутников…'
                  : 'Слабый сигнал — выйдите на открытое место')}
            </p>
          )}
          <div className="mt-1.5 space-y-1">
            {data && <Stage1PhaseBanner data={data} />}
            <EngineerOrderBanner onShowOnMap={handleShowOrderOnMap} />
          </div>
        </div>
        <div className="mt-2 flex items-center justify-center gap-1.5 md:gap-2">
          <button
            type="button"
            className={`${actionBtnClass} ${
              mapOpen ? 'border-sideA bg-sideA/15 text-sideA' : 'border-zinc-600 text-zinc-300'
            }`}
            onClick={toggleMap}
          >
            Карта {mapOpen ? '▼' : '▲'}
          </button>
          <EngineerChatSheet
            side={side}
            variant="toggle"
            open={chatOpen}
            onOpenChange={handleChatOpenChange}
            buttonClassName={actionBtnClass}
          />
          <LogoutButton className={`${actionBtnClass} border-zinc-600`} />
        </div>
      </header>

      {mapOpen ? (
        <div className="relative flex-1 flex flex-col md:flex-row min-h-0 min-h-[50vh]">
          <div className="map-page flex-1 min-h-[40vh] md:min-h-0">
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
                renderAdminPopup={({ kind, data: target }) => {
                  if (kind === 'landmark') return null;
                  return (
                    <EngineerTargetPopup
                      kind={kind}
                      data={target}
                      orderNote={orderMatchesSelection ? latest?.note : null}
                      stage1Phase={data.stage1_phase}
                      side={side}
                      onClose={() => setMapSelection(null)}
                      onOpenCapture={() => navigate(`/point/${target.id}`)}
                    />
                  );
                }}
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
              onClose={() => handleChatOpenChange(false)}
              className="shrink-0 h-[min(45vh,400px)] md:h-auto md:w-[min(100%,22rem)] border-t md:border-t-0 md:border-l"
            />
          )}
        </div>
      ) : (
        <EngineerChatAside
          side={side}
          onClose={() => handleChatOpenChange(false)}
          className="flex-1 min-h-0"
        />
      )}
    </div>
  );
}
