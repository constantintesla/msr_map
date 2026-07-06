import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  beginPointCapture,
  fetchStatus,
  holdConfirm,
  submitPostFilmReport,
  syncHoldPoint,
  type StatusData,
} from '../api/client';
import LogoutButton from '../components/LogoutButton';
import EngineerOrderBanner from '../components/EngineerOrderBanner';
import EngineerChatSheet from '../components/EngineerChatSheet';
import EngineerRadioBadge from '../components/EngineerRadioBadge';
import GameMap from '../components/GameMap';
import Stage1PhaseBanner from '../components/Stage1PhaseBanner';
import { useGeolocation } from '../hooks/useGeolocation';
import { useEngineerLocationPing } from '../hooks/useEngineerLocationPing';
import { useWakeLock } from '../hooks/useWakeLock';
import { FENCE_RADIUS_M, ACCURACY_FENCE_BONUS_MAX_M, isInsideFenceWithAccuracy } from '../utils/haversine';
import { isCaptureAccuracyOk } from '../utils/geoFilter';
import { applyGpsOffset } from '../utils/gpsOffset';
import GpsStatusIndicator from '../components/GpsStatusIndicator';
import { stage1CaptureBlocked } from '../utils/pointControl';
import { parseServerUtc, secondsUntilDeadline } from '../utils/serverDate';
import { engineerSocketHub } from '../ws/hubs';
import 'leaflet/dist/leaflet.css';

const POST_HOLD_SEC_FALLBACK = 600;

function formatCountdown(totalSec: number): string {
  const m = Math.floor(totalSec / 60);
  const s = totalSec % 60;
  return `${m}:${s.toString().padStart(2, '0')}`;
}

export default function PointPage({ pointId: pointIdProp }: { pointId?: number } = {}) {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  const pointId = pointIdProp ?? Number(id);
  const side = localStorage.getItem('side') || 'A';
  const userId = Number(localStorage.getItem('user_id') || 0);
  const isEngineer = localStorage.getItem('role') === 'engineer';
  const wasCapturingRef = useRef(false);

  const [data, setData] = useState<StatusData | null>(null);
  const [inside, setInside] = useState(false);
  const [statusMsg, setStatusMsg] = useState('');
  const [captureCode, setCaptureCode] = useState('');
  const [videoFile, setVideoFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);

  useWakeLock(true);
  const { position: rawPosition, error: geoError, gpsStatus, refresh } = useGeolocation();
  const position = useMemo(
    () => applyGpsOffset(rawPosition, data?.gps_lat_offset ?? 0, data?.gps_lon_offset ?? 0),
    [rawPosition, data?.gps_lat_offset, data?.gps_lon_offset],
  );
  useEngineerLocationPing(position);

  const point = data?.points.find((p) => p.id === pointId);
  const isStage3Context = data?.current_stage === 3 && !!point;
  const canAssaultPost = isStage3Context && !!point && !point.destroyed && side === 'A';
  const isStage3Post = canAssaultPost;
  const isStage1Kt = data?.current_stage !== 3 && !!point && !point.destroyed;
  const stage1Recapturable = data?.stage1_recapturable ?? true;
  const stage1State = stage1CaptureBlocked(point, side, stage1Recapturable);
  const stage1Blocked = isStage1Kt && stage1State.blocked;
  const ownedByUs = isStage1Kt && stage1State.ownedByUs;
  const lockedByEnemy = isStage1Kt && stage1State.lockedByEnemy;
  const underAttack = isStage1Kt && stage1State.underAttack;
  const isRecapturing =
    isStage1Kt && !!point?.held_by && point.held_by === side && !!point?.side && point.side !== side;
  const isHolder =
    !!point?.held_by &&
    point.held_by === side &&
    (point.held_by_user_id == null || point.held_by_user_id === userId);
  const isStage1HoldBlocked =
    isStage1Kt &&
    !stage1Blocked &&
    !isHolder &&
    data?.stage1_phase === 'hold' &&
    !point?.stage1_capturable;
  const usesHoldButton = (isStage1Kt && !stage1Blocked) || isStage3Post;
  const captureHoldSec = data?.point_capture_seconds ?? 120;
  const postHoldSec = data?.post_hold_seconds ?? POST_HOLD_SEC_FALLBACK;
  const deadmanSec = isStage1Kt
    ? (data?.point_hold_ping_seconds ?? data?.hold_deadman_seconds ?? 120)
    : isStage3Post
      ? (data?.post_hold_ping_seconds ?? data?.hold_deadman_seconds ?? 120)
      : (data?.hold_deadman_seconds ?? 120);
  const fenceRadius = data?.capture_radius_m ?? FENCE_RADIUS_M;
  const fenceDisabled = data?.disable_capture_distance ?? false;
  const gpsBonusMax = data?.gps_accuracy_bonus_max_m ?? ACCURACY_FENCE_BONUS_MAX_M;
  const minCaptureAccuracy = data?.gps_min_accuracy_for_capture_m ?? 0;
  const captureAccuracyOk = isCaptureAccuracyOk(position?.accuracy, minCaptureAccuracy);
  const captureBlocked = !fenceDisabled && minCaptureAccuracy > 0 && !captureAccuracyOk;
  const captureDisabled = (!fenceDisabled && !inside) || captureBlocked;
  const gameRunning = data?.game_status === 'running';
  const gameBlockedMsg =
    data?.game_status === 'paused'
      ? 'Игра на паузе. Захват временно недоступен.'
      : 'Игра не началась. Дождитесь «Старт» от администратора.';

  const heldByOther =
    !!point?.held_by && (point.held_by !== side || (point.held_by_user_id != null && point.held_by_user_id !== userId));

  const pingLeftSec = useMemo(() => {
    if (!isHolder || !point?.last_ping_at) return deadmanSec;
    const left = secondsUntilDeadline(point.last_ping_at, deadmanSec);
    return left ?? deadmanSec;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tick drives countdown refresh
  }, [point?.last_ping_at, isHolder, deadmanSec, tick]);

  const holdElapsedSec = useMemo(() => {
    if (!point?.held_by) return point?.hold_elapsed_sec ?? 0;
    const startMs = parseServerUtc(point.hold_started_at);
    if (startMs == null) return point.hold_elapsed_sec ?? 0;
    return Math.max(point.hold_elapsed_sec ?? 0, Math.floor((Date.now() - startMs) / 1000));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- tick drives elapsed refresh
  }, [point?.held_by, point?.hold_started_at, point?.hold_elapsed_sec, tick]);

  const captureLeftSec = useMemo(() => {
    if (point?.hold_ready) return 0;
    return Math.max(0, captureHoldSec - holdElapsedSec);
  }, [point?.hold_ready, captureHoldSec, holdElapsedSec]);

  const loadStatus = useCallback(() => {
    return fetchStatus().then(setData).catch(console.error);
  }, []);

  const returnToEngineerMap = useCallback(() => {
    if (!isEngineer) return;
    wasCapturingRef.current = false;
    navigate('/engineer');
  }, [isEngineer, navigate]);

  useEffect(() => {
    if (isStage1Kt && isHolder) wasCapturingRef.current = true;
  }, [isStage1Kt, isHolder]);

  useEffect(() => {
    if (!isEngineer || !isStage1Kt || !ownedByUs) return;
    if (!wasCapturingRef.current) return;
    returnToEngineerMap();
  }, [isEngineer, isStage1Kt, ownedByUs, returnToEngineerMap]);

  useEffect(() => {
    void syncHoldPoint(pointId)
      .then(() => loadStatus())
      .catch(console.error);
    const poll = setInterval(loadStatus, 10000);
    return () => clearInterval(poll);
  }, [pointId, loadStatus]);

  useEffect(() => {
    return engineerSocketHub.subscribe((packet) => {
      if (packet.e === 'game_state' || packet.e === 'settings_update') {
        void loadStatus();
      }
    });
  }, [loadStatus]);

  useEffect(() => {
    const timer = setInterval(() => setTick((n) => n + 1), 1000);
    return () => clearInterval(timer);
  }, []);

  useEffect(() => {
    if (!point) return;
    const inZone =
      fenceDisabled ||
      (position
        ? isInsideFenceWithAccuracy(
            position.lat,
            position.lon,
            point.lat,
            point.lon,
            fenceRadius,
            position.accuracy,
            gpsBonusMax
          )
        : false);
    setInside(inZone);
  }, [position, point, fenceRadius, fenceDisabled, gpsBonusMax]);

  useEffect(() => {
    if (!isHolder || !isStage1Kt || ownedByUs || captureLeftSec > 0) return;
    void syncHoldPoint(pointId)
      .then(() => loadStatus())
      .catch(() => {});
  }, [isHolder, isStage1Kt, ownedByUs, captureLeftSec, pointId, loadStatus]);

  useEffect(() => {
    if (!isHolder || ownedByUs || pingLeftSec > 0) return;
    void syncHoldPoint(pointId)
      .then(() => loadStatus())
      .then(() => setStatusMsg('Удержание прекращено — не нажали вовремя'))
      .catch(() => {});
  }, [isHolder, ownedByUs, pingLeftSec, pointId, loadStatus]);

  const handleBeginCapture = async () => {
    if (!gameRunning) {
      setStatusMsg(gameBlockedMsg);
      return;
    }
    if (!fenceDisabled && captureBlocked) {
      setStatusMsg(`Подождите уточнения GPS (нужно ≤${minCaptureAccuracy}м)`);
      return;
    }
    if (!fenceDisabled && !inside) {
      setStatusMsg(`Подойдите к точке (${fenceRadius}м)`);
      return;
    }
    if (!position && !fenceDisabled) {
      setStatusMsg('Ожидание GPS…');
      return;
    }
    if (captureCode.length < 4) {
      setStatusMsg('Введите код от штаба');
      return;
    }
    if (heldByOther) return;
    if (stage1Blocked) {
      setStatusMsg(lockedByEnemy ? 'Точка уже захвачена' : 'Точка недоступна');
      return;
    }
    setLoading(true);
    setStatusMsg('');
    try {
      const lat = position?.lat ?? point!.lat;
      const lon = position?.lon ?? point!.lon;
      const accuracy = position?.accuracy;
      const r = await beginPointCapture(pointId, captureCode, side, lat, lon, accuracy);
      wasCapturingRef.current = true;
      setStatusMsg(r.message || 'Захват начат');
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          points: prev.points.map((p) =>
            p.id === pointId
              ? {
                  ...p,
                  held_by: side,
                  held_by_user_id: userId || p.held_by_user_id,
                  last_ping_at: (r.last_ping_at as string | undefined) ?? p.last_ping_at,
                  hold_elapsed_sec: r.hold_elapsed_sec ?? 0,
                  hold_ready: r.hold_ready ?? false,
                }
              : p
          ),
        };
      });
      await loadStatus();
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmHold = async () => {
    if (!gameRunning) {
      setStatusMsg(gameBlockedMsg);
      return;
    }
    if (!fenceDisabled && !inside) {
      setStatusMsg(`Подойдите к точке (${fenceRadius}м)`);
      return;
    }
    if (heldByOther) return;
    setLoading(true);
    setStatusMsg('');
    try {
      const r = await holdConfirm(pointId, side);
      setData((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          points: prev.points.map((p) =>
            p.id === pointId
              ? {
                  ...p,
                  held_by: side,
                  held_by_user_id: userId || p.held_by_user_id,
                  last_ping_at: (r.last_ping_at as string | undefined) ?? p.last_ping_at,
                  hold_elapsed_sec: r.hold_elapsed_sec ?? p.hold_elapsed_sec,
                  hold_ready: r.hold_ready ?? p.hold_ready,
                }
              : p
          ),
        };
      });
      if (isStage3Post) {
        if (r.hold_ready) {
          setStatusMsg('Удержание завершено — загрузите видео объективного контроля');
        } else {
          const left = Math.max(0, postHoldSec - (r.hold_elapsed_sec || 0));
          setStatusMsg(`Удержание поста: осталось ${Math.ceil(left / 60)} мин`);
        }
      } else if (isStage1Kt) {
        if (r.hold_ready || ownedByUs) {
          setStatusMsg('КТ захвачена');
        } else if (deadmanSec < captureHoldSec) {
          setStatusMsg('Присутствие подтверждено');
        } else {
          const left = Math.max(0, captureHoldSec - (r.hold_elapsed_sec || 0));
          setStatusMsg(`Захват: осталось ${formatCountdown(left)}`);
        }
      } else {
        setStatusMsg('Удержание подтверждено');
      }
      await loadStatus();
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  const handlePostFilmReport = async () => {
    if (!gameRunning) {
      setStatusMsg(gameBlockedMsg);
      return;
    }
    if (!videoFile) {
      setStatusMsg('Выберите видео объективного контроля');
      return;
    }
    if (!fenceDisabled && !inside) {
      setStatusMsg(`Подойдите к посту (${fenceRadius}м)`);
      return;
    }
    setLoading(true);
    try {
      const lat = position?.lat ?? point!.lat;
      const lon = position?.lon ?? point!.lon;
      const result = await submitPostFilmReport(pointId, side, lat, lon, videoFile);
      setStatusMsg(result.message || `Пост подорван! +${result.bonus}`);
      setVideoFile(null);
      await loadStatus();
    } catch (e) {
      setStatusMsg(e instanceof Error ? e.message : 'Ошибка');
    } finally {
      setLoading(false);
    }
  };

  if (!data || !point) {
    return <div className="min-h-dvh flex items-center justify-center">Загрузка...</div>;
  }

  const postHoldMinutes = Math.round(postHoldSec / 60);
  const holdRequiredSec = isStage3Post ? postHoldSec : captureHoldSec;
  const holdProgress = Math.min(100, (holdElapsedSec / holdRequiredSec) * 100);
  const captureMinutes = Math.round(captureHoldSec / 60);
  const deadmanMinutes = Math.round(deadmanSec / 60);
  /** Этап 1: кнопка нужна только если захват дольше интервала dead-man */
  const stage1NeedsPing = isStage1Kt && deadmanSec < captureHoldSec;
  const captureComplete = ownedByUs || !!point.hold_ready;
  const showCaptureTimer = usesHoldButton && isHolder && !captureComplete && isStage1Kt;
  const showPingTimer =
    isHolder &&
    !ownedByUs &&
    !point.hold_ready &&
    (isStage3Post || stage1NeedsPing);
  const showHoldButton =
    (isStage3Post && isHolder && !point.hold_ready) ||
    (isStage1Kt && isHolder && stage1NeedsPing && !captureComplete);

  return (
    <div className="min-h-dvh flex flex-col">
      <header className="p-4 border-b border-zinc-800 z-10 flex justify-between items-start gap-2">
        <div className="min-w-0">
          <Link
            to="/engineer"
            className="inline-flex items-center gap-1 text-xs text-zinc-500 hover:text-zinc-300 mb-1"
          >
            ← Карта
          </Link>
          <h1 className="font-bold text-xl">{point.name}</h1>
          <p className="text-sm text-zinc-400">
            {isStage3Context
              ? side === 'A'
                ? 'Этап 3 · Штурм поста · ЛК'
                : 'Этап 3 · Оборона поста · СБГ'
              : `Этап 1 · Сторона ${side}`}
          </p>
          <div className="mt-1.5 space-y-2">
            <EngineerRadioBadge />
            <EngineerOrderBanner />
            {data && <Stage1PhaseBanner data={data} />}
          </div>
          {usesHoldButton && isHolder && !ownedByUs && (
            <p className="mt-2 text-xs text-zinc-500">
              {isStage3Post
                ? `Подтверждайте удержание каждые ${deadmanMinutes} мин. Иначе захват сбросится.`
                : stage1NeedsPing
                  ? `Подтверждайте присутствие каждые ${deadmanMinutes} мин, пока идёт захват.`
                  : `Оставайтесь в зоне ${captureMinutes} мин — захват завершится сам, нажимать не нужно.`}
            </p>
          )}
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <EngineerChatSheet side={side as 'A' | 'B'} />
          <LogoutButton />
        </div>
      </header>

      {!gameRunning && !stage1Blocked && (
        <section className="shrink-0 px-4 py-3 border-b border-warning/40 bg-warning/10 text-center">
          <p className="text-sm text-warning">{gameBlockedMsg}</p>
        </section>
      )}

      {ownedByUs && (
        <section className="shrink-0 p-6 border-b border-zinc-800 bg-zinc-950/80 text-center space-y-2">
          <p className="text-green-400 text-lg font-medium">КТ захвачена вашей стороной</p>
        </section>
      )}

      {underAttack && (
        <section className="shrink-0 p-6 border-b border-zinc-800 bg-zinc-950/80 text-center space-y-2">
          <p className="text-sideB text-lg font-medium">Противник перезахватывает КТ</p>
        </section>
      )}

      {lockedByEnemy && (
        <section className="shrink-0 p-6 border-b border-zinc-800 bg-zinc-950/80 text-center space-y-2">
          <p className="text-sideB text-lg font-medium">КТ захвачена противником</p>
          <p className="text-sm text-zinc-500">Повторный захват невозможен</p>
        </section>
      )}

      {isRecapturing && (
        <section className="shrink-0 px-4 py-3 border-b border-warning/40 bg-warning/10 text-center">
          <p className="text-sm text-warning">Перезахват КТ — удерживайте точку до завершения</p>
        </section>
      )}

      {isStage1HoldBlocked && (
        <section className="shrink-0 px-4 py-3 border-b border-zinc-800 bg-zinc-900/80 text-center">
          <p className="text-sm text-zinc-400">Точка не в активном наборе текущего слота</p>
        </section>
      )}

      {canAssaultPost && !isHolder && (
        <section className="shrink-0 p-6 border-b border-zinc-800 bg-zinc-950/80 space-y-4">
          <p className="text-sm text-zinc-400 text-center">Перейди по QR, войди и введи код от штаба</p>
          <input
            className="input w-full max-w-xs mx-auto block text-center text-2xl tracking-widest font-mono"
            inputMode="numeric"
            maxLength={6}
            placeholder="Код от штаба"
            value={captureCode}
            onChange={(e) => setCaptureCode(e.target.value.replace(/\D/g, ''))}
          />
          <button
            type="button"
            className="btn w-full max-w-md mx-auto block bg-sideA text-white text-lg py-4 min-h-touch disabled:opacity-50"
            disabled={loading || heldByOther || !gameRunning || captureDisabled}
            onClick={() => void handleBeginCapture()}
          >
            {loading ? '…' : 'Начать штурм'}
          </button>
          {heldByOther && (
            <p className="text-sideB text-sm text-center">
              {point.held_by !== side
                ? 'Пост уже удерживается другой стороной'
                : 'Пост уже удерживается другим инженером'}
            </p>
          )}
          {!heldByOther && !fenceDisabled && !inside && (
            <p className="text-warning text-sm text-center">Подойдите в зону ({fenceRadius}м)</p>
          )}
        </section>
      )}

      {isStage1Kt && !stage1Blocked && !isHolder && !isStage1HoldBlocked && (
        <section className="shrink-0 p-6 border-b border-zinc-800 bg-zinc-950/80 space-y-4">
          <p className="text-sm text-zinc-400 text-center">Перейди по QR, войди и введи код от штаба</p>
          <input
            className="input w-full max-w-xs mx-auto block text-center text-2xl tracking-widest font-mono"
            inputMode="numeric"
            maxLength={6}
            placeholder="Код от штаба"
            value={captureCode}
            onChange={(e) => setCaptureCode(e.target.value.replace(/\D/g, ''))}
          />
          <button
            type="button"
            className="btn w-full max-w-md mx-auto block bg-sideA text-white text-lg py-4 min-h-touch disabled:opacity-50"
            disabled={loading || heldByOther || !gameRunning || captureDisabled}
            onClick={() => void handleBeginCapture()}
          >
            {loading ? '…' : 'Начать захват'}
          </button>
          {heldByOther && !stage1Blocked && (
            <p className="text-sideB text-sm text-center">
              {point.held_by !== side
                ? 'Точка уже удерживается другой стороной'
                : 'Точка уже удерживается другим инженером'}
            </p>
          )}
          {!heldByOther && !fenceDisabled && !inside && (
            <p className="text-warning text-sm text-center">Подойдите в зону ({fenceRadius}м)</p>
          )}
        </section>
      )}

      {usesHoldButton && ((isStage3Post && isHolder && !point.hold_ready) || (isStage1Kt && isHolder)) && (
        <section className="shrink-0 p-6 border-b border-zinc-800 bg-zinc-950/80 text-center space-y-4">
          <div className="space-y-3">
            {showCaptureTimer && (
              <div>
                <p className="text-xs uppercase tracking-wide text-zinc-500 mb-1">До завершения захвата</p>
                <p className="text-4xl font-mono font-bold tabular-nums text-sideA">
                  {formatCountdown(captureLeftSec)}
                </p>
              </div>
            )}
            {showPingTimer && (
              <div>
                <p className="text-xs uppercase tracking-wide text-zinc-500 mb-1">
                  {isStage3Post ? 'До следующего подтверждения' : 'До подтверждения присутствия'}
                </p>
                <p
                  className={`text-5xl font-mono font-bold tabular-nums ${
                    pingLeftSec <= 30 ? 'text-warning' : 'text-zinc-100'
                  }`}
                >
                  {formatCountdown(pingLeftSec)}
                </p>
              </div>
            )}
          </div>

          {showHoldButton && (
            <button
              type="button"
              className="btn w-full max-w-md mx-auto bg-sideA text-white text-lg py-4 min-h-touch disabled:opacity-50"
              disabled={loading || heldByOther || !gameRunning || captureDisabled}
              onClick={() => void handleConfirmHold()}
            >
              {loading ? '…' : isStage1Kt ? 'Подтвердить присутствие' : 'Подтвердить удержание'}
            </button>
          )}

          {isStage1Kt && isHolder && !stage1NeedsPing && !captureComplete && (
            <p className="text-sm text-zinc-400">Захват идёт — дождитесь окончания таймера</p>
          )}

          {heldByOther && !stage1Blocked && (
            <p className="text-sideB text-sm">
              {point.held_by !== side
                ? 'Точка уже удерживается другой стороной'
                : 'Точка уже удерживается другим инженером'}
            </p>
          )}
          {!heldByOther && !fenceDisabled && !inside && (
            <p className="text-warning text-sm">Подойдите в зону ({fenceRadius}м)</p>
          )}
        </section>
      )}

      <div className="map-page flex-1 min-h-[28vh]">
        <GameMap
          data={data}
          center={[point.lat, point.lon]}
          zoom={17}
          showFence={{ lat: point.lat, lon: point.lon, radius: fenceRadius }}
          userPosition={position}
        />
      </div>

      <div className="p-4 space-y-3 border-t border-zinc-800">
        {usesHoldButton && (isStage1Kt || isStage3Post) && (
          <div className="space-y-1">
            <div className="flex justify-between text-xs text-zinc-500">
              <span>{isStage3Post ? 'Удержание поста' : 'Захват КТ'}</span>
              <span>
                {Math.floor(holdElapsedSec / 60)}:
                {(holdElapsedSec % 60).toString().padStart(2, '0')}/
                {isStage3Post ? postHoldMinutes : captureMinutes} мин
              </span>
            </div>
            <div className="h-2 bg-zinc-800 rounded overflow-hidden">
              <div
                className={`h-full transition-all ${point.hold_ready ? 'bg-green-500' : 'bg-sideA'}`}
                style={{ width: `${holdProgress}%` }}
              />
            </div>
            {isStage3Post && point.hold_ready && (
              <p className="text-green-400 text-sm">Удержание завершено — загрузите видео ОК</p>
            )}
            {isStage1Kt && ownedByUs && (
              <p className="text-green-400 text-sm">КТ захвачена</p>
            )}
            {isStage1Kt && isHolder && !point.hold_ready && !ownedByUs && (
              <p className="text-zinc-400 text-sm">Идёт захват — не выходите из зоны</p>
            )}
          </div>
        )}

        {isStage3Context && point.pending_admin && (
          <p className="text-warning text-sm">
            Пост подорван. Видеоотчёт в чате командования. Ожидайте подтверждения штаба.
          </p>
        )}
        {isStage3Context && point.admin_confirmed && (
          <p className="text-green-400 text-sm">Пост подтверждён штабом и выведен из игры.</p>
        )}

        {canAssaultPost && point.hold_ready && (
          <>
            <p className="text-sm text-green-400">Загрузите видео объективного контроля подрыва поста.</p>
            <label className="block">
              <span className="sr-only">Видео объективного контроля</span>
              <input
                type="file"
                accept="video/mp4,video/webm,video/quicktime,.mp4,.webm,.mov"
                className="input w-full text-sm"
                onChange={(e) => setVideoFile(e.target.files?.[0] ?? null)}
              />
            </label>
            <button
              type="button"
              className="btn w-full bg-warning text-black disabled:opacity-50 min-h-touch"
              onClick={() => void handlePostFilmReport()}
              disabled={loading || !gameRunning || captureDisabled || !videoFile}
            >
              Отправить видео ОК
            </button>
          </>
        )}

        {isStage3Context && !point.destroyed && side !== 'A' && (
          <p className="text-zinc-500 text-sm">Сторона СБГ обороняется — действия в приложении не требуются.</p>
        )}

        <GpsStatusIndicator
          gpsStatus={gpsStatus}
          accuracy={position?.accuracy ?? null}
          error={geoError}
          onRefresh={refresh}
          captureBlocked={captureBlocked}
          minCaptureAccuracy={minCaptureAccuracy}
        />
        {statusMsg && <p className="text-sm text-zinc-400">{statusMsg}</p>}
      </div>
    </div>
  );
}
