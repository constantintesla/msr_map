import { useEffect, useMemo, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  fetchCommanderEngineers,
  fetchCommanderFeed,
  fetchCommanderStatus,
  fetchEngineerLocations,
  type CommanderFeedItem,
  type CommanderStatusData,
  type EngineerLocation,
  type EngineerPoolItem,
} from '../api/client';
import { commanderSocketHub } from '../ws/hubs';
import GameMap from '../components/GameMap';
import ChatPanel from '../components/ChatPanel';
import CommanderEngineersPanel from '../components/CommanderEngineersPanel';
import CommanderOrderPopup from '../components/CommanderOrderPopup';
import Stage1PhaseBanner from '../components/Stage1PhaseBanner';
import FieldOrdersPanel from '../components/FieldOrdersPanel';
import LogoutButton from '../components/LogoutButton';
import { useIsNarrow } from '../hooks/useMediaQuery';
import { pointController, isStage1Captured, isStage1Capturing } from '../utils/pointControl';
import 'leaflet/dist/leaflet.css';

type PointItem = CommanderStatusData['points'][number];
type TabId = 'points' | 'loot' | 'feed' | 'chat' | 'engineers';

function pointStatusLabel(p: PointItem, mySide: string, stage: number): { text: string; className: string; dot: string } {
  if (stage === 3 && p.destroyed) {
    if (p.admin_confirmed) return { text: 'выключен', className: 'text-zinc-500', dot: 'bg-zinc-600' };
    if (p.pending_admin) return { text: 'ждёт штаб', className: 'text-warning', dot: 'bg-warning' };
    const ours = p.destroyed_by_side === mySide;
    return {
      text: ours ? 'подорван нами' : 'подорван врагом',
      className: ours ? 'text-green-400' : 'text-sideB',
      dot: ours ? 'bg-green-500' : 'bg-sideB',
    };
  }

  const controller = pointController(p);
  if (controller === mySide) {
    if (stage === 3 && p.hold_ready) {
      return { text: 'готов к подрыву', className: 'text-green-400', dot: 'bg-green-500' };
    }
    if (stage === 1 && isStage1Captured(p)) {
      return { text: 'захвачена', className: 'text-green-400', dot: 'bg-green-500' };
    }
    if (stage === 1 && isStage1Capturing(p) && p.held_by === mySide) {
      const min = Math.floor((p.hold_elapsed_sec || 0) / 60);
      const sec = (p.hold_elapsed_sec || 0) % 60;
      return {
        text: `захват ${min}:${sec.toString().padStart(2, '0')}`,
        className: 'text-warning',
        dot: 'bg-warning',
      };
    }
    return { text: 'удерживаем', className: 'text-green-400', dot: 'bg-green-500' };
  }
  if (controller && controller !== mySide) {
    if (stage === 1 && isStage1Captured(p)) {
      return {
        text: 'захвачена врагом',
        className: controller === 'A' ? 'text-sideA' : 'text-sideB',
        dot: controller === 'A' ? 'bg-sideA' : 'bg-sideB',
      };
    }
    if (stage === 1 && isStage1Capturing(p)) {
      return {
        text: 'захват противника',
        className: controller === 'A' ? 'text-sideA' : 'text-sideB',
        dot: controller === 'A' ? 'bg-sideA' : 'bg-sideB',
      };
    }
    return {
      text: 'захват противника',
      className: controller === 'A' ? 'text-sideA' : 'text-sideB',
      dot: controller === 'A' ? 'bg-sideA' : 'bg-sideB',
    };
  }
  return { text: 'свободна', className: 'text-zinc-500', dot: 'bg-zinc-600' };
}

function cacheStatusLabel(
  c: CommanderStatusData['caches'][number],
  mySide: string
): { text: string; className: string } {
  if (c.cache_kind === 'film_loot') {
    if (c.delivered) {
      const ours = c.delivered_by_side === mySide;
      return {
        text: ours ? 'сдан нами' : 'сдан противником',
        className: ours ? 'text-green-400' : 'text-sideB',
      };
    }
    if (c.pending_delivery_admin) {
      const ours = c.delivered_by_side === mySide;
      return {
        text: ours ? 'фото с базы, ждёт штаба' : 'фото у противника',
        className: 'text-warning',
      };
    }
    if (c.destroyed) {
      if (c.pending_admin) {
        return { text: 'видеоотчёт, ждёт штаба', className: 'text-warning' };
      }
      const ours = c.destroyed_by_side === mySide;
      return {
        text: ours ? 'вскрыт нами' : 'вскрыт противником',
        className: ours ? 'text-green-400' : 'text-sideB',
      };
    }
    return { text: 'не вскрыт', className: 'text-zinc-500' };
  }
  if (c.destroyed) return { text: 'подорван', className: 'text-zinc-500' };
  return { text: 'активен', className: 'text-zinc-400' };
}

function PointRow({
  p,
  mySide,
  stage,
  onSelect,
}: {
  p: PointItem;
  mySide: string;
  stage: number;
  onSelect?: () => void;
}) {
  const st = pointStatusLabel(p, mySide, stage);
  return (
    <li
      className={`flex items-center gap-2 py-2 border-b border-zinc-800/80 last:border-0 ${onSelect ? 'cursor-pointer hover:bg-zinc-800/40 -mx-2 px-2 rounded' : ''}`}
      onClick={onSelect}
      onKeyDown={onSelect ? (e) => e.key === 'Enter' && onSelect() : undefined}
      role={onSelect ? 'button' : undefined}
      tabIndex={onSelect ? 0 : undefined}
    >
      <span className={`w-2 h-2 rounded-full shrink-0 ${st.dot}`} />
      <span className="flex-1 min-w-0 font-medium text-sm truncate">{p.name}</span>
      <span className={`text-xs shrink-0 ${st.className}`}>{st.text}</span>
    </li>
  );
}

function StatPill({
  label,
  count,
  active,
  onClick,
  variant,
}: {
  label: string;
  count: number;
  active: boolean;
  onClick: () => void;
  variant: 'green' | 'enemy' | 'neutral' | 'done';
}) {
  const styles = {
    green: { active: 'border-green-500/50 bg-green-500/10', count: 'text-green-400' },
    enemy: { active: 'border-sideB/50 bg-sideB/10', count: 'text-sideB' },
    neutral: { active: 'border-zinc-600 bg-zinc-900', count: 'text-zinc-300' },
    done: { active: 'border-zinc-600 bg-zinc-900', count: 'text-zinc-400' },
  }[variant];

  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg px-2.5 py-1.5 text-left border transition-colors ${
        active ? styles.active : 'border-zinc-800 bg-zinc-950 hover:border-zinc-700'
      }`}
    >
      <span className={`block text-lg font-bold leading-none ${active ? styles.count : 'text-zinc-300'}`}>
        {count}
      </span>
      <span className="block text-[10px] text-zinc-500 mt-0.5 uppercase tracking-wide">{label}</span>
    </button>
  );
}

export default function CommanderPage() {
  const location = useLocation();
  const isNarrow = useIsNarrow();
  const [mapOpen, setMapOpen] = useState(true);
  const [data, setData] = useState<CommanderStatusData | null>(null);
  const [feed, setFeed] = useState<CommanderFeedItem[]>([]);
  const [error, setError] = useState('');
  const [tab, setTab] = useState<TabId>('points');
  const [pointFilter, setPointFilter] = useState<'all' | 'ours' | 'enemy' | 'free' | 'done'>('all');
  const [engineers, setEngineers] = useState<EngineerLocation[]>([]);
  const [poolEngineers, setPoolEngineers] = useState<EngineerPoolItem[]>([]);
  const [mapSelection, setMapSelection] = useState<{ kind: 'point' | 'cache'; id: number } | null>(null);
  const [ordersRefresh, setOrdersRefresh] = useState(0);

  const mySide = data?.viewer_side || localStorage.getItem('side') || 'A';

  const openOrder = (kind: 'point' | 'cache', id: number) => setMapSelection({ kind, id });

  useEffect(() => {
    const load = () =>
      Promise.all([fetchCommanderStatus(), fetchCommanderFeed(), fetchEngineerLocations()])
        .then(([status, feedRes, eng]) => {
          setData(status);
          setFeed(feedRes.items);
          setEngineers(eng);
          setError('');
        })
        .catch((e) => setError(e instanceof Error ? e.message : 'Ошибка загрузки'));

    load();
    const id = setInterval(load, 8000);

    const unsub = commanderSocketHub.subscribe((packet) => {
      if (
        packet.e === 'location' ||
        packet.e === 'chat' ||
        packet.e === 'lpd_channel' ||
        packet.e === 'field_order_update' ||
        packet.e === 'stage2_issued' ||
        packet.e === 'hold_start' ||
        packet.e === 'hold_ping' ||
        packet.e === 'point_capture' ||
        packet.e === 'point_hold_ready' ||
        packet.e === 'hold_leave' ||
        packet.e === 'hold_expired'
      ) {
        void load();
        if (packet.e === 'field_order_update') setOrdersRefresh((n) => n + 1);
      }
    });

    fetchCommanderEngineers().then(setPoolEngineers).catch(() => {});

    return () => {
      clearInterval(id);
      unsub();
    };
  }, [location.pathname]);

  const grouped = useMemo(() => {
    if (!data) return null;
    const stage = data.current_stage;
    const ours: PointItem[] = [];
    const enemy: PointItem[] = [];
    const free: PointItem[] = [];
    const done: PointItem[] = [];

    for (const p of data.points) {
      const controller = pointController(p);
      if (stage === 3 && p.destroyed) done.push(p);
      else if (controller === mySide) ours.push(p);
      else if (controller) enemy.push(p);
      else free.push(p);
    }
    return { ours, enemy, free, done, all: data.points };
  }, [data, mySide]);

  const filteredPoints = useMemo(() => {
    if (!grouped) return [];
    if (pointFilter === 'all') return grouped.all;
    return grouped[pointFilter];
  }, [grouped, pointFilter]);

  const events = useMemo(() => feed.filter((f) => !f.is_broadcast).slice(-25).reverse(), [feed]);

  if (error && !data) {
    return (
      <div className="min-h-dvh flex flex-col items-center justify-center p-6 text-center gap-4">
        <p className="text-sideB">{error}</p>
        <LogoutButton />
      </div>
    );
  }

  if (!data || !grouped) {
    return <div className="min-h-dvh flex items-center justify-center text-zinc-500">Загрузка…</div>;
  }

  const stageLabel = data.stages?.find((s) => s.stage === data.current_stage)?.label ?? `Этап ${data.current_stage}`;
  const gameRunning = data.game_status === 'running';

  const tabs: { id: TabId; label: string; badge?: number }[] = [
    { id: 'points', label: 'Точки', badge: data.points.length },
    ...(data.caches.length > 0 ? [{ id: 'loot' as TabId, label: 'Лут', badge: data.caches.length }] : []),
    { id: 'feed', label: 'События', badge: events.length > 0 ? events.length : undefined },
    { id: 'engineers', label: 'Инженеры' },
    { id: 'chat', label: 'Чат' },
  ];

  return (
    <div className="h-dvh flex flex-col overflow-hidden bg-bg">
      <header className="shrink-0 px-4 py-3 border-b border-zinc-800 bg-zinc-950/90 backdrop-blur-sm z-30">
        <div className="flex items-center gap-3">
          <div
            className={`w-1 h-10 rounded-full shrink-0 ${mySide === 'A' ? 'bg-sideA' : 'bg-sideB'}`}
            aria-hidden
          />
          <div className="flex-1 min-w-0">
            <h1 className={`font-bold text-lg leading-tight ${mySide === 'A' ? 'text-sideA' : 'text-sideB'}`}>
              {data.side_label}
            </h1>
            <p className="text-xs text-zinc-500 truncate">
              {stageLabel}
              <span className="mx-1.5 text-zinc-700">·</span>
              <span className={gameRunning ? 'text-green-500' : 'text-zinc-400'}>{data.game_status}</span>
            </p>
            <Stage1PhaseBanner data={data} className="mt-1" />
            {data.stage2_active_loot && (
              <div className="mt-2 p-2 rounded-lg border border-warning/40 bg-warning/10 text-xs space-y-1">
                <p className="font-bold text-warning">Задача-2: {data.stage2_active_loot.name}</p>
                <p className="font-mono text-zinc-300">
                  {data.stage2_active_loot.lat.toFixed(6)}, {data.stage2_active_loot.lon.toFixed(6)}
                </p>
                <p>
                  Код: <span className="font-mono font-bold">{data.stage2_active_loot.code}</span>
                </p>
                <button
                  type="button"
                  className="text-warning underline"
                  onClick={() => {
                    setMapSelection({ kind: 'cache', id: data.stage2_active_loot!.cache_id });
                  }}
                >
                  Показать на карте
                </button>
                <button
                  type="button"
                  className="ml-3 text-zinc-400 underline"
                  onClick={() => {
                    const t = data.stage2_active_loot!;
                    void navigator.clipboard.writeText(
                      `${t.name}\n${t.lat}, ${t.lon}\nКод: ${t.code}`,
                    );
                  }}
                >
                  Копировать
                </button>
              </div>
            )}
          </div>
          <div className="flex items-center gap-2 shrink-0">
            {isNarrow && (
              <button
                type="button"
                className={`btn text-sm border min-h-0 py-1.5 px-3 ${
                  mapOpen ? 'border-sideA bg-sideA/15 text-sideA' : 'border-zinc-600 text-zinc-300'
                }`}
                onClick={() => setMapOpen(!mapOpen)}
              >
                Карта {mapOpen ? '▼' : '▲'}
              </button>
            )}
            <LogoutButton />
          </div>
        </div>
      </header>

      <div className="flex-1 flex flex-col landscape-phone:flex-row md:flex-row min-h-0">
        {(!isNarrow || mapOpen) && (
        <div className="map-page flex-1 min-h-[32vh] max-md:max-h-[45dvh] landscape-phone:max-h-none landscape-phone:min-h-0 md:min-h-0 relative border-b landscape-phone:border-b-0 md:border-b-0 landscape-phone:border-r md:border-r border-zinc-800">
          <GameMap
            data={data}
            showRadii
            engineers={engineers}
            viewerSide={data.viewer_side}
            adminSelection={mapSelection}
            onPointClick={(p) => openOrder('point', p.id)}
            onCacheClick={(c) => openOrder('cache', c.id)}
            onAdminPopupClose={() => setMapSelection(null)}
            renderAdminPopup={({ kind, data: target }) => (
              <CommanderOrderPopup
                targetKind={kind}
                target={{ id: target.id, name: target.name, lat: target.lat, lon: target.lon }}
                engineers={poolEngineers}
                pointData={kind === 'point' ? (target as CommanderStatusData['points'][number]) : undefined}
                stage1Phase={data.stage1_phase}
                side={mySide}
                onClose={() => setMapSelection(null)}
                onSent={() => {
                  setMapSelection(null);
                  setOrdersRefresh((n) => n + 1);
                }}
              />
            )}
          />
        </div>
        )}

        <aside className="relative z-10 flex-1 min-h-0 landscape-phone:flex-none landscape-phone:w-[min(100%,22rem)] md:w-[min(100%,22rem)] lg:w-96 shrink-0 flex flex-col bg-zinc-950">
          <nav className="shrink-0 flex border-b border-zinc-800 overflow-x-auto" role="tablist">
            {tabs.map((t) => (
              <button
                key={t.id}
                type="button"
                role="tab"
                aria-selected={tab === t.id}
                onClick={() => setTab(t.id)}
                className={`flex-1 py-3 text-sm font-medium transition-colors relative whitespace-nowrap min-w-[4.5rem] px-1 ${
                  tab === t.id ? 'text-zinc-100' : 'text-zinc-500 hover:text-zinc-300'
                }`}
              >
                {t.label}
                {t.badge !== undefined && (
                  <span
                    className={`ml-1 text-[10px] px-1.5 py-0.5 rounded-full ${
                      tab === t.id ? 'bg-zinc-800 text-zinc-300' : 'bg-zinc-900 text-zinc-600'
                    }`}
                  >
                    {t.badge}
                  </span>
                )}
                {tab === t.id && (
                  <span
                    className={`absolute bottom-0 left-2 right-2 h-0.5 rounded-full ${
                      mySide === 'A' ? 'bg-sideA' : 'bg-sideB'
                    }`}
                  />
                )}
              </button>
            ))}
          </nav>

          <div className="flex-1 overflow-y-auto overscroll-contain min-h-0 flex flex-col">
            {tab === 'chat' && (
              <ChatPanel mode="commander" side={mySide as 'A' | 'B'} className="flex-1 min-h-0" />
            )}

            {tab === 'engineers' && (
              <div className="flex flex-col min-h-0 flex-1">
                <FieldOrdersPanel mode="commander" side={mySide as 'A' | 'B'} refreshToken={ordersRefresh} />
                <div className="flex-1 overflow-y-auto min-h-0">
                  <CommanderEngineersPanel side={mySide as 'A' | 'B'} />
                </div>
              </div>
            )}

            {tab === 'points' && (
              <div className="p-3 space-y-3">
                <div className="grid grid-cols-4 gap-1.5">
                  <StatPill
                    label="наши"
                    count={grouped.ours.length}
                    active={pointFilter === 'ours'}
                    onClick={() => setPointFilter(pointFilter === 'ours' ? 'all' : 'ours')}
                    variant="green"
                  />
                  <StatPill
                    label="враг"
                    count={grouped.enemy.length}
                    active={pointFilter === 'enemy'}
                    onClick={() => setPointFilter(pointFilter === 'enemy' ? 'all' : 'enemy')}
                    variant="enemy"
                  />
                  <StatPill
                    label="своб."
                    count={grouped.free.length}
                    active={pointFilter === 'free'}
                    onClick={() => setPointFilter(pointFilter === 'free' ? 'all' : 'free')}
                    variant="neutral"
                  />
                  <StatPill
                    label="готово"
                    count={grouped.done.length}
                    active={pointFilter === 'done'}
                    onClick={() => setPointFilter(pointFilter === 'done' ? 'all' : 'done')}
                    variant="done"
                  />
                </div>

                {pointFilter !== 'all' && (
                  <button
                    type="button"
                    className="text-xs text-zinc-500 underline"
                    onClick={() => setPointFilter('all')}
                  >
                    Показать все точки
                  </button>
                )}

                <ul className="rounded-xl border border-zinc-800 bg-zinc-900/50 px-3">
                  {filteredPoints.length === 0 && (
                    <li className="py-6 text-center text-sm text-zinc-600">Нет точек в этой группе</li>
                  )}
                  {filteredPoints.map((p) => (
                    <PointRow
                      key={p.id}
                      p={p}
                      mySide={mySide}
                      stage={data.current_stage}
                      onSelect={() => openOrder('point', p.id)}
                    />
                  ))}
                </ul>
              </div>
            )}

            {tab === 'loot' && (
              <div className="p-3">
                <ul className="space-y-2">
                  {data.caches.map((c) => {
                    const st = cacheStatusLabel(c, mySide);
                    return (
                      <li
                        key={c.id}
                        className="rounded-xl border border-zinc-800 bg-zinc-900/50 px-3 py-2.5 flex items-start justify-between gap-2 cursor-pointer hover:border-zinc-700"
                        onClick={() => openOrder('cache', c.id)}
                      >
                        <span className="text-sm font-medium leading-snug">{c.name}</span>
                        <span className={`text-xs shrink-0 ${st.className}`}>{st.text}</span>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}

            {tab === 'feed' && (
              <div className="p-3">
                <section>
                  <h2 className="text-[10px] font-bold uppercase tracking-wider text-zinc-500 mb-2">
                    События игры
                  </h2>
                  {events.length === 0 && (
                    <p className="text-sm text-zinc-600 py-8 text-center">Событий пока нет</p>
                  )}
                  <div className="space-y-0">
                    {events.map((item) => (
                      <div
                        key={item.id}
                        className="py-2 border-b border-zinc-800/80 last:border-0 text-xs leading-relaxed"
                      >
                        <span className="text-zinc-600 font-mono">
                          {new Date(item.created_at).toLocaleTimeString()}
                        </span>
                        <span className="text-zinc-400 ml-2">{item.text}</span>
                      </div>
                    ))}
                  </div>
                </section>
              </div>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
