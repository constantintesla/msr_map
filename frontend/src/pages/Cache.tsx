import { useCallback, useEffect, useMemo, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  fetchStatus,
  submitBreachCode,
  submitDeliverReport,
  submitFilmReport,
  submitUnlockCode,
  type StatusData,
} from '../api/client';
import LogoutButton from '../components/LogoutButton';
import EngineerOrderBanner from '../components/EngineerOrderBanner';
import EngineerChatSheet from '../components/EngineerChatSheet';
import EngineerRadioBadge from '../components/EngineerRadioBadge';
import GameMap from '../components/GameMap';
import { useGeolocation } from '../hooks/useGeolocation';
import { useEngineerLocationPing } from '../hooks/useEngineerLocationPing';
import { useWakeLock } from '../hooks/useWakeLock';
import { FENCE_RADIUS_M, ACCURACY_FENCE_BONUS_MAX_M, isInsideFenceWithAccuracy } from '../utils/haversine';
import { isCaptureAccuracyOk } from '../utils/geoFilter';
import { applyGpsOffset } from '../utils/gpsOffset';
import GpsStatusIndicator from '../components/GpsStatusIndicator';
import 'leaflet/dist/leaflet.css';

export interface CachePageProps {
  cacheId: number;
  qrToken: string;
}

export default function CachePage({ cacheId, qrToken }: CachePageProps) {
  const side = localStorage.getItem('side') || 'A';

  const [data, setData] = useState<StatusData | null>(null);
  const [message, setMessage] = useState('');
  const [loading, setLoading] = useState(false);
  const [code, setCode] = useState('');
  const [codeVerified, setCodeVerified] = useState(false);
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [photoFile, setPhotoFile] = useState<File | null>(null);

  useWakeLock(true);
  const { position: rawPosition, error: geoError, gpsStatus, refresh } = useGeolocation();
  const position = useMemo(
    () => applyGpsOffset(rawPosition, data?.gps_lat_offset ?? 0, data?.gps_lon_offset ?? 0),
    [rawPosition, data?.gps_lat_offset, data?.gps_lon_offset],
  );
  useEngineerLocationPing(position);

  const load = useCallback(() => fetchStatus().then(setData).catch(console.error), []);

  useEffect(() => {
    load();
    const t = setInterval(load, 10000);
    return () => clearInterval(t);
  }, [load]);

  const cache = data?.caches.find((c) => c.id === cacheId);
  const isFilmLoot = cache?.cache_kind === 'film_loot';
  const isMertvyak = cache?.cache_kind === 'mertvyak';
  const isFilmPassage = (cache?.loot_variant || 'film_passage') === 'film_passage';
  const isBoxDirect = cache?.loot_variant === 'box_direct';
  const fenceRadius = data?.capture_radius_m ?? FENCE_RADIUS_M;
  const fenceDisabled = data?.disable_capture_distance ?? false;
  const gpsBonusMax = data?.gps_accuracy_bonus_max_m ?? ACCURACY_FENCE_BONUS_MAX_M;
  const minCaptureAccuracy = data?.gps_min_accuracy_for_capture_m ?? 0;
  const captureAccuracyOk = isCaptureAccuracyOk(position?.accuracy, minCaptureAccuracy);
  const captureBlocked = !fenceDisabled && minCaptureAccuracy > 0 && !captureAccuracyOk;

  const atBox = useMemo(() => {
    if (!cache) return false;
    if (fenceDisabled) return true;
    if (!position) return false;
    return isInsideFenceWithAccuracy(
      position.lat,
      position.lon,
      cache.lat,
      cache.lon,
      fenceRadius,
      position.accuracy,
      gpsBonusMax,
    );
  }, [cache, fenceDisabled, position, fenceRadius, gpsBonusMax]);

  const captureDisabled = (!fenceDisabled && !atBox) || captureBlocked;

  const handleVerifyCode = async () => {
    if (code.length < 4) {
      setMessage('Введите код от штаба');
      return;
    }
    if (!fenceDisabled && captureBlocked) {
      setMessage(`Подождите уточнения GPS (нужно ≤${minCaptureAccuracy}м)`);
      return;
    }
    if (!fenceDisabled && !atBox) {
      setMessage(`Подойдите к объекту (${fenceRadius}м)`);
      return;
    }
    setLoading(true);
    setMessage('');
    try {
      const lat = position?.lat ?? cache!.lat;
      const lon = position?.lon ?? cache!.lon;
      const accuracy = position?.accuracy;
      if (isBoxDirect) {
        const result = await submitUnlockCode(cacheId, code, side, qrToken, lat, lon, accuracy);
        setMessage(result.message || 'Ящик разблокирован');
        setCode('');
      } else {
        const result = await submitBreachCode(cacheId, code, side, qrToken, lat, lon, accuracy);
        setCodeVerified(true);
        setMessage(result.message || 'Код принят');
      }
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  const handleFilmReport = async () => {
    if (!videoFile) {
      setMessage('Выберите видео объективного контроля');
      return;
    }
    setLoading(true);
    try {
      const lat = position?.lat ?? cache!.lat;
      const lon = position?.lon ?? cache!.lon;
      const result = await submitFilmReport(cacheId, side, lat, lon, qrToken, videoFile);
      setMessage(result.message || 'Подрыв зафиксирован');
      setVideoFile(null);
      setCodeVerified(false);
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  const handleDeliverReport = async () => {
    if (!photoFile) {
      setMessage('Выберите фото доставки на базу');
      return;
    }
    setLoading(true);
    try {
      const lat = position?.lat ?? cache!.lat;
      const lon = position?.lon ?? cache!.lon;
      const result = await submitDeliverReport(cacheId, side, lat, lon, qrToken, photoFile);
      setMessage(result.message || 'Фотоотчёт отправлен');
      setPhotoFile(null);
      await load();
    } catch (e) {
      setMessage(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  if (!data) {
    return <div className="min-h-dvh flex items-center justify-center">Загрузка...</div>;
  }

  if (!cache) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center gap-3 p-6 text-center">
        <p className="text-lg font-bold">Цель ещё не выдана</p>
        <p className="text-sm text-zinc-400">
          Этот ящик пока недоступен. Дождитесь выдачи цели штабом.
        </p>
        <LogoutButton />
      </div>
    );
  }

  const breached = cache.destroyed;
  const delivered = cache.delivered;
  const deliveryReported = cache.delivery_reported;
  const pendingDelivery = cache.pending_delivery_admin;
  const breachedByOther = breached && cache.destroyed_by_side && cache.destroyed_by_side !== side;
  const breachedByUs = breached && cache.destroyed_by_side === side;
  const lootLabel = isFilmPassage ? 'Проход с плёнкой' : isBoxDirect ? 'Ящик с табличкой' : 'Ящик';

  return (
    <div className="min-h-dvh flex flex-col">
      <header className="p-4 border-b border-zinc-800 z-10 flex justify-between items-start gap-2">
        <div>
          <Link
            to="/engineer"
            className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 mb-1"
          >
            ← Карта
          </Link>
          <h1 className="font-bold">{cache.name}</h1>
          <p className="text-sm text-zinc-400">
            {isFilmLoot ? `Задача-2 · ${lootLabel}` : isMertvyak ? 'Этап 3 · Мертвяк' : 'Схрон'} · {side}
          </p>
          {isFilmLoot && (
            <p className="text-xs text-zinc-500 mt-1">
              Страница открыта по QR. Код выдаёт штаб.
            </p>
          )}
          <div className="mt-1.5 space-y-2">
            <EngineerRadioBadge />
            <EngineerOrderBanner />
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <EngineerChatSheet side={side as 'A' | 'B'} />
          <LogoutButton />
        </div>
      </header>

      <div className="map-page flex-1">
        <GameMap
          data={data}
          center={[cache.lat, cache.lon]}
          zoom={17}
          showFence={{ lat: cache.lat, lon: cache.lon, radius: fenceRadius }}
          userPosition={position}
          viewerSide={side}
        />
      </div>

      <div className="p-4 space-y-4 border-t border-zinc-800">
        {isFilmLoot && (
          <span className={atBox ? 'text-green-400' : 'text-warning'}>
            {fenceDisabled
              ? '● У объекта (тест: без геозоны)'
              : atBox
                ? `● У объекта (${fenceRadius}м)`
                : `○ До объекта >${fenceRadius}м`}
          </span>
        )}
        <GpsStatusIndicator
          gpsStatus={gpsStatus}
          accuracy={position?.accuracy ?? null}
          error={geoError}
          onRefresh={refresh}
          captureBlocked={captureBlocked}
          minCaptureAccuracy={minCaptureAccuracy}
        />

        {isMertvyak && (
          <p className="text-zinc-400 text-sm">
            Мертвяк настраивается штабом в админке. С телефона действий не требуется.
          </p>
        )}

        {breachedByOther && isFilmLoot && (
          <p className="text-sideB">Объект уже взят стороной {cache.destroyed_by_side}.</p>
        )}

        {delivered && (
          <p className="text-zinc-400">Ящик сдан на базу стороной {cache.delivered_by_side}.</p>
        )}

        {pendingDelivery && (
          <p className="text-warning text-sm">Фотоотчёт в чате. Ожидайте подтверждения штабом.</p>
        )}

        {isFilmLoot && !breached && !breachedByOther && !codeVerified && (
          <>
            <p className="text-sm text-zinc-400">Введите код от штаба.</p>
            <input
              className="input w-full font-mono text-lg tracking-widest"
              placeholder="Код"
              value={code}
              maxLength={6}
              inputMode="numeric"
              onChange={(e) => setCode(e.target.value.replace(/\D/g, ''))}
            />
            <button
              type="button"
              className="btn w-full bg-sideA text-white disabled:opacity-50 min-h-touch"
              onClick={handleVerifyCode}
              disabled={loading || code.length < 4 || captureDisabled}
            >
              ПОДТВЕРДИТЬ КОД
            </button>
          </>
        )}

        {isFilmLoot && isFilmPassage && codeVerified && !breached && (
          <>
            <p className="text-sm text-green-400">Код принят. Загрузите видео подрыва плёнки.</p>
            <label className="block">
              <span className="text-xs text-zinc-500 mb-1 block">Видео (MP4, WebM, MOV)</span>
              <input
                type="file"
                accept="video/mp4,video/webm,video/quicktime,video/*"
                capture="environment"
                className="input w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-zinc-700 file:px-3 file:py-1.5 file:text-zinc-100"
                onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)}
              />
            </label>
            {videoFile && <p className="text-xs text-zinc-500 truncate">Выбрано: {videoFile.name}</p>}
            <button
              type="button"
              className="btn w-full bg-warning text-black disabled:opacity-50 min-h-touch"
              onClick={handleFilmReport}
              disabled={loading || !videoFile}
            >
              ПОДОРВАТЬ · ОТПРАВИТЬ ВИДЕО
            </button>
          </>
        )}

        {isFilmLoot && breachedByUs && !deliveryReported && !delivered && (
          <>
            <p className="text-sm text-zinc-400">
              Заберите ящик и доставьте на базу. Загрузите фото для подтверждения.
            </p>
            <label className="block">
              <span className="text-xs text-zinc-500 mb-1 block">Фото (JPEG, PNG, WebP)</span>
              <input
                type="file"
                accept="image/jpeg,image/png,image/webp,image/*"
                capture="environment"
                className="input w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-zinc-700 file:px-3 file:py-1.5 file:text-zinc-100"
                onChange={(e) => setPhotoFile(e.target.files?.[0] ?? null)}
              />
            </label>
            {photoFile && <p className="text-xs text-zinc-500 truncate">Выбрано: {photoFile.name}</p>}
            <button
              type="button"
              className="btn w-full bg-sideA text-white disabled:opacity-50 min-h-touch"
              onClick={handleDeliverReport}
              disabled={loading || !photoFile}
            >
              ОТПРАВИТЬ ФОТО С БАЗЫ
            </button>
          </>
        )}

        {message && <p className="text-sm">{message}</p>}
      </div>
    </div>
  );
}
