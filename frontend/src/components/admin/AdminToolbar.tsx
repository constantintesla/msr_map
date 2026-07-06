import type { ChangeEvent, ReactNode } from 'react';
import { useEffect, useState } from 'react';
import type { ScoreBreakdownData, SideScoreBreakdown, StatusData } from '../../api/client';
import { fetchScoreBreakdown } from '../../api/client';
import LogoutButton from '../LogoutButton';
import Stage1PhaseBanner from '../Stage1PhaseBanner';

interface AdminToolbarProps {
  data: StatusData;
  gameStatus: { text: string; className: string };
  actionMsg: string;
  error: string;
  settingsOpen: boolean;
  missionOpen: boolean;
  lootPanelOpen: boolean;
  chatOpen: boolean;
  tracksOpen: boolean;
  hasFilmLoot: boolean;
  onStart: () => void;
  onPause: () => void;
  onReset: () => void;
  onStartStage1Slot: () => void;
  onKmlReload: () => void;
  onKmzChange: (e: ChangeEvent<HTMLInputElement>) => void;
  onToggleSettings: () => void;
  onToggleMission: () => void;
  onToggleLoot: () => void;
  onExportLogs: () => void;
  onToggleChat: () => void;
  onToggleTracks: () => void;
  onStageChange: (stage: number) => void;
  mapEditMode: boolean;
  onToggleMapEdit: () => void;
  gameIdle: boolean;
  onWipeMap: () => void;
}

function ScoreBreakdownLines({ bd }: { bd: SideScoreBreakdown }) {
  const rows = [
    ['Удержание', bd.hold],
    ['Захваты', bd.captures],
    ['Вскрытие', bd.loot_breach],
    ['Доставка', bd.loot_deliver],
    ['Посты', bd.posts],
    ['Схроны', bd.caches],
  ].filter(([, v]) => v > 0);
  if (rows.length === 0) {
    return <span className="text-zinc-500">нет начислений</span>;
  }
  return (
    <ul className="space-y-0.5">
      {rows.map(([label, value]) => (
        <li key={label} className="flex justify-between gap-3">
          <span className="text-zinc-500">{label}</span>
          <span className="tabular-nums">{value}</span>
        </li>
      ))}
    </ul>
  );
}

function ToolGroup({ label, first, children }: { label: string; first?: boolean; children: ReactNode }) {
  return (
    <div
      className={`flex items-center gap-1.5 pl-2 ${first ? '' : 'border-l border-zinc-700'}`}
    >
      <span className="text-[10px] uppercase tracking-wide text-zinc-600 hidden sm:inline shrink-0">{label}</span>
      <div className="flex flex-wrap items-center gap-1.5">{children}</div>
    </div>
  );
}

export default function AdminToolbar({
  data,
  gameStatus,
  actionMsg,
  error,
  settingsOpen,
  missionOpen,
  lootPanelOpen,
  chatOpen,
  tracksOpen,
  hasFilmLoot,
  onStart,
  onPause,
  onReset,
  onStartStage1Slot,
  onKmlReload,
  onKmzChange,
  onToggleSettings,
  onToggleMission,
  onToggleLoot,
  onExportLogs,
  onToggleChat,
  onToggleTracks,
  onStageChange,
  mapEditMode,
  onToggleMapEdit,
  gameIdle,
  onWipeMap,
}: AdminToolbarProps) {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const [scoreOpen, setScoreOpen] = useState(false);
  const [breakdown, setBreakdown] = useState<ScoreBreakdownData | null>(null);
  const stageLabel =
    data.stages?.find((s) => s.stage === data.current_stage)?.label ?? `Этап ${data.current_stage}`;

  useEffect(() => {
    if (data.game_status === 'idle') {
      setBreakdown(null);
      return;
    }
    let cancelled = false;
    fetchScoreBreakdown()
      .then((bd) => {
        if (!cancelled) setBreakdown(bd);
      })
      .catch(() => {
        if (!cancelled) setBreakdown(null);
      });
    return () => {
      cancelled = true;
    };
  }, [data.updated_at, data.game_status, data.score_a, data.score_b]);

  return (
    <header className="shrink-0 border-b border-zinc-800 z-20 bg-bg/95 no-print">
      <div className="px-3 pt-2 pb-1.5 max-md:py-2 flex items-start gap-2 md:gap-3">
        <div
          className="w-1 h-10 rounded-full shrink-0 bg-sideA max-md:hidden"
          aria-hidden
        />
        <div className="flex-1 min-w-0">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <h1 className="font-bold text-base md:text-lg leading-tight text-zinc-100">Штаб</h1>
            <span className="text-[11px] md:text-xs text-zinc-500">{stageLabel}</span>
            <span className={`text-[11px] md:text-xs font-medium ${gameStatus.className}`}>{gameStatus.text}</span>
          </div>
          <Stage1PhaseBanner data={data} className="mt-0.5 max-md:line-clamp-1" />
          {(actionMsg || error) && (
            <div className="mt-0.5 flex flex-wrap gap-2">
              {actionMsg && <span className="text-[11px] md:text-xs text-green-400">{actionMsg}</span>}
              {error && <span className="text-[11px] md:text-xs text-sideB">{error}</span>}
            </div>
          )}
        </div>
        <div className="flex items-center gap-1.5 shrink-0 relative">
          <button
            type="button"
            className="flex items-center gap-1.5 text-sm max-md:gap-1 rounded-lg focus:outline-none focus-visible:ring-1 focus-visible:ring-sideA"
            aria-label="Счёт игры"
            title="Набранные очки ЛК и СБГ — нажмите для детализации"
            onClick={() => setScoreOpen((v) => !v)}
          >
            <div className="rounded-lg bg-zinc-900 border border-zinc-800 px-2 py-0.5 md:px-2.5 md:py-1 text-center">
              <span className="text-[9px] md:text-[10px] text-zinc-500 block">ЛК</span>
              <span className="font-bold text-sm text-sideA">{data.score_a ?? 0}</span>
            </div>
            <div className="rounded-lg bg-zinc-900 border border-zinc-800 px-2 py-0.5 md:px-2.5 md:py-1 text-center">
              <span className="text-[9px] md:text-[10px] text-zinc-500 block">СБГ</span>
              <span className="font-bold text-sm text-sideB">{data.score_b ?? 0}</span>
            </div>
          </button>
          {scoreOpen && breakdown && (
            <div className="absolute right-0 top-full mt-1 z-30 w-56 rounded-lg border border-zinc-700 bg-zinc-900 p-2.5 text-[11px] shadow-xl">
              <div className="font-semibold text-zinc-300 mb-2">Детализация счёта</div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <div className="text-sideA font-medium mb-1">ЛК</div>
                  <ScoreBreakdownLines bd={breakdown.breakdown_a} />
                </div>
                <div>
                  <div className="text-sideB font-medium mb-1">СБГ</div>
                  <ScoreBreakdownLines bd={breakdown.breakdown_b} />
                </div>
              </div>
            </div>
          )}
          <button
            type="button"
            className="md:hidden btn border border-zinc-600 text-xs min-h-0 py-1 px-2 shrink-0"
            onClick={() => setMobileMenuOpen((v) => !v)}
            aria-expanded={mobileMenuOpen}
          >
            {mobileMenuOpen ? '▲' : 'Ещё'}
          </button>
          <LogoutButton />
        </div>
      </div>

      {/* Mobile: только старт / пауза / сброс */}
      <div className="md:hidden px-3 pb-2 flex flex-wrap items-center gap-1.5 [&_.btn]:min-h-0 [&_.btn]:py-1.5 [&_.btn]:px-2 [&_.btn]:text-xs">
        <button
          type="button"
          className="btn bg-green-600 text-white text-sm disabled:opacity-40"
          disabled={data.game_status === 'running'}
          onClick={onStart}
        >
          Старт
        </button>
        <button
          type="button"
          className="btn bg-warning text-black text-sm disabled:opacity-40"
          disabled={data.game_status !== 'running'}
          onClick={onPause}
        >
          Пауза
        </button>
        <button type="button" className="btn bg-sideB text-white text-sm" onClick={onReset}>
          Сброс
        </button>
        {data.current_stage === 1 && data.game_status === 'running' && data.stage1_phase === 'idle' && (
          <button
            type="button"
            className="btn bg-sideA text-white text-sm"
            title="Запустить первый слот захвата КТ"
            onClick={onStartStage1Slot}
          >
            Запустить слот 1
          </button>
        )}
      </div>

      <div
        className={`md:hidden px-3 pb-2 space-y-2 [&_.btn]:min-h-0 [&_.btn]:py-1.5 [&_.btn]:px-2 [&_.btn]:text-xs ${
          mobileMenuOpen ? '' : 'hidden'
        }`}
      >
        <div className="flex gap-1.5">
          {(data.stages || []).filter((s) => s.stage !== 2).map((s) => (
            <button
              key={s.stage}
              type="button"
              className={`flex-1 rounded-lg px-1.5 py-1.5 text-xs font-bold transition-colors ${
                data.current_stage === s.stage
                  ? s.stage === 1
                    ? 'bg-sideA text-white'
                    : s.stage === 3
                      ? 'bg-warning text-black'
                      : 'bg-zinc-200 text-black'
                  : 'border border-zinc-700 text-zinc-400'
              }`}
              onClick={() => {
                onStageChange(s.stage);
                setMobileMenuOpen(false);
              }}
            >
              {s.label}
            </button>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          <button type="button" className="btn border border-zinc-600 text-sm" onClick={onKmlReload}>
            KML
          </button>
          <label className="btn border border-zinc-600 text-sm cursor-pointer">
            KMZ
            <input type="file" accept=".kmz,.kml" className="hidden" onChange={onKmzChange} />
          </label>
          {gameIdle && (
            <button
              type="button"
              className={`btn text-sm border ${
                mapEditMode ? 'border-sideA bg-sideA/20 text-sideA' : 'border-zinc-600'
              }`}
              onClick={() => {
                onToggleMapEdit();
                setMobileMenuOpen(false);
              }}
            >
              {mapEditMode ? 'Завершить редактирование' : 'Редактировать карту'}
            </button>
          )}
          {gameIdle && (
            <button
              type="button"
              className="btn text-sm border border-sideB text-sideB"
              onClick={() => {
                onWipeMap();
                setMobileMenuOpen(false);
              }}
            >
              Удалить всё
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5">
          {data.current_stage === 1 && (
            <button
              type="button"
              className={`btn text-sm border ${
                missionOpen ? 'border-sideA bg-sideA/25 text-sideA' : 'border-sideA text-sideA'
              }`}
              onClick={() => {
                onToggleMission();
                setMobileMenuOpen(false);
              }}
            >
              {missionOpen ? 'Скрыть КТ' : 'КТ и коды'}
            </button>
          )}
          {hasFilmLoot && (
            <button
              type="button"
              className={`btn text-sm border ${
                lootPanelOpen ? 'border-warning bg-warning/25 text-warning' : 'border-warning text-warning'
              }`}
              onClick={() => {
                onToggleLoot();
                setMobileMenuOpen(false);
              }}
            >
              {lootPanelOpen ? 'Скрыть ящики' : 'Ящики'}
            </button>
          )}
          {data.current_stage === 3 && (
            <button
              type="button"
              className={`btn text-sm border ${
                missionOpen ? 'border-warning bg-warning/25 text-warning' : 'border-warning text-warning'
              }`}
              onClick={() => {
                onToggleMission();
                setMobileMenuOpen(false);
              }}
            >
              {missionOpen ? 'Скрыть мертвяки' : 'Мертвяки'}
            </button>
          )}
          <button
            type="button"
            className={`btn text-sm border ${settingsOpen ? 'border-sideA bg-sideA/20 text-sideA' : 'border-zinc-600'}`}
            onClick={() => {
              onToggleSettings();
              setMobileMenuOpen(false);
            }}
          >
            Настройки
          </button>
          <button
            type="button"
            className={`btn text-sm border ${chatOpen ? 'border-sideA bg-sideA/15 text-sideA' : 'border-zinc-600'}`}
            onClick={() => {
              onToggleChat();
              setMobileMenuOpen(false);
            }}
          >
            Чат
          </button>
          <button
            type="button"
            className={`btn text-sm border ${tracksOpen ? 'border-cyan-500 bg-cyan-500/15 text-cyan-400' : 'border-zinc-600'}`}
            onClick={() => {
              onToggleTracks();
              setMobileMenuOpen(false);
            }}
          >
            {tracksOpen ? 'Скрыть треки' : 'Треки'}
          </button>
          <button type="button" className="btn border border-zinc-600 text-sm" onClick={onExportLogs}>
            CSV
          </button>
        </div>
      </div>

      {/* Desktop: все кнопки в одной строке */}
      <div className="hidden md:flex px-3 pb-3 flex-wrap items-center gap-2">
        <ToolGroup label="Игра" first>
          <button
            type="button"
            className="btn bg-green-600 text-white text-sm disabled:opacity-40"
            disabled={data.game_status === 'running'}
            title="Разрешить инженерам захват и действия на карте"
            onClick={onStart}
          >
            Старт
          </button>
          <button
            type="button"
            className="btn bg-warning text-black text-sm disabled:opacity-40"
            disabled={data.game_status !== 'running'}
            title="Временно заблокировать захват (данные сохраняются)"
            onClick={onPause}
          >
            Пауза
          </button>
          <button
            type="button"
            className="btn bg-sideB text-white text-sm"
            title="Обнулить счёт, захваты и вернуть этап 1"
            onClick={onReset}
          >
            Сброс
          </button>
        </ToolGroup>

        {data.current_stage === 1 && data.game_status === 'running' && (
          <ToolGroup label="Этап 1">
            {data.stage1_phase === 'idle' && (
              <button
                type="button"
                className="btn bg-sideA text-white text-sm"
                title="Запустить первый слот захвата КТ"
                onClick={onStartStage1Slot}
              >
                Запустить слот 1
              </button>
            )}
          </ToolGroup>
        )}

        <ToolGroup label="Карта">
          <button type="button" className="btn border border-zinc-600 text-sm" onClick={onKmlReload}>
            KML пресет
          </button>
          <label className="btn border border-zinc-600 text-sm cursor-pointer">
            KMZ
            <input type="file" accept=".kmz,.kml" className="hidden" onChange={onKmzChange} />
          </label>
          {gameIdle && (
            <button
              type="button"
              className="btn border border-sideB text-sideB text-sm"
              title="Удалить все точки, схроны и базы с карты (только до старта)"
              onClick={onWipeMap}
            >
              Удалить всё
            </button>
          )}
        </ToolGroup>

        <ToolGroup label="Материалы">
          {data.current_stage === 1 && (
            <button
              type="button"
              className={`btn text-sm border ${
                missionOpen ? 'border-sideA bg-sideA/25 text-sideA' : 'border-sideA text-sideA'
              }`}
              onClick={() => {
                onToggleMission();
                setMobileMenuOpen(false);
              }}
            >
              {missionOpen ? 'Скрыть КТ' : 'КТ и коды'}
            </button>
          )}
          {hasFilmLoot && (
            <button
              type="button"
              className={`btn text-sm border ${
                lootPanelOpen ? 'border-warning bg-warning/25 text-warning' : 'border-warning text-warning'
              }`}
              onClick={() => {
                onToggleLoot();
                setMobileMenuOpen(false);
              }}
            >
              {lootPanelOpen ? 'Скрыть ящики' : 'Ящики и коды'}
            </button>
          )}
          {data.current_stage === 3 && (
            <button
              type="button"
              className={`btn text-sm border ${
                missionOpen ? 'border-warning bg-warning/25 text-warning' : 'border-warning text-warning'
              }`}
              onClick={() => {
                onToggleMission();
                setMobileMenuOpen(false);
              }}
            >
              {missionOpen ? 'Скрыть мертвяки' : 'Мертвяки'}
            </button>
          )}
        </ToolGroup>

        <ToolGroup label="Сервис">
          <button
            type="button"
            className={`btn text-sm border ${settingsOpen ? 'border-sideA bg-sideA/20 text-sideA' : 'border-zinc-600'}`}
            onClick={() => {
              onToggleSettings();
              setMobileMenuOpen(false);
            }}
          >
            {settingsOpen ? 'Скрыть настройки' : 'Настройки'}
          </button>
          <button
            type="button"
            className={`btn text-sm border ${chatOpen ? 'border-sideA bg-sideA/15 text-sideA' : 'border-zinc-600'}`}
            onClick={() => {
              onToggleChat();
              setMobileMenuOpen(false);
            }}
          >
            {chatOpen ? 'Скрыть чат' : 'Чат'}
          </button>
          <button
            type="button"
            className={`btn text-sm border ${tracksOpen ? 'border-cyan-500 bg-cyan-500/15 text-cyan-400' : 'border-zinc-600'}`}
            onClick={() => {
              onToggleTracks();
              setMobileMenuOpen(false);
            }}
          >
            {tracksOpen ? 'Скрыть треки' : 'Треки GPS'}
          </button>
          <button type="button" className="btn border border-zinc-600 text-sm" onClick={onExportLogs}>
            CSV лог
          </button>
        </ToolGroup>
      </div>
    </header>
  );
}
