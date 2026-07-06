import type { MapCreateTarget } from '../GameMap';

interface AdminMapEditorBarProps {
  mapEditMode: boolean;
  hideToggleOnMobile?: boolean;
  createTarget: MapCreateTarget | null;
  mertvyakCreateSide: 'A' | 'B';
  landmarkCreateKind: 'base' | 'start' | 'base_start';
  landmarkCreateSide: 'A' | 'B';
  onToggleEditMode: () => void;
  onSetCreateTarget: (target: MapCreateTarget | null) => void;
  onMertvyakSideChange: (side: 'A' | 'B') => void;
  onLandmarkKindChange: (kind: 'base' | 'start' | 'base_start') => void;
  onLandmarkSideChange: (side: 'A' | 'B') => void;
}

export default function AdminMapEditorBar({
  mapEditMode,
  hideToggleOnMobile = false,
  createTarget,
  mertvyakCreateSide,
  landmarkCreateKind,
  landmarkCreateSide,
  onToggleEditMode,
  onSetCreateTarget,
  onMertvyakSideChange,
  onLandmarkKindChange,
  onLandmarkSideChange,
}: AdminMapEditorBarProps) {
  return (
    <div className="no-print shrink-0 px-3 py-2 max-md:py-1.5 border-b border-zinc-800 bg-zinc-900/80 space-y-2 [&_.btn]:max-md:min-h-0 [&_.btn]:max-md:py-1 [&_.btn]:max-md:text-xs">
      <div className={`flex flex-wrap items-center gap-2 ${hideToggleOnMobile ? 'max-md:hidden' : ''}`}>
        <button
          type="button"
          className={`btn text-sm border ${
            mapEditMode ? 'border-sideA bg-sideA/20 text-sideA' : 'border-zinc-600'
          }`}
          onClick={onToggleEditMode}
        >
          {mapEditMode ? 'Завершить редактирование' : 'Редактировать карту'}
        </button>
        {mapEditMode && (
          <span className="text-xs text-zinc-500">
            Перетащите маркер или выберите тип и кликните по карте
          </span>
        )}
      </div>
      {mapEditMode && (
        <div className="flex flex-wrap gap-1 items-center">
          <button
            type="button"
            className={`btn text-xs border py-1 min-h-0 ${
              createTarget?.kind === 'point' && createTarget.stage === 1
                ? 'border-sideA bg-sideA/20 text-sideA'
                : 'border-zinc-600'
            }`}
            onClick={() => onSetCreateTarget({ kind: 'point', stage: 1 })}
          >
            + КТ
          </button>
          <button
            type="button"
            className={`btn text-xs border py-1 min-h-0 ${
              createTarget?.kind === 'cache' && createTarget.cache_kind === 'film_loot'
                ? 'border-warning bg-warning/20 text-warning'
                : 'border-zinc-600'
            }`}
            onClick={() => onSetCreateTarget({ kind: 'cache', stage: 2, cache_kind: 'film_loot' })}
          >
            + Ящик
          </button>
          <button
            type="button"
            className={`btn text-xs border py-1 min-h-0 ${
              createTarget?.kind === 'point' && createTarget.stage === 3
                ? 'border-sideA bg-sideA/20 text-sideA'
                : 'border-zinc-600'
            }`}
            onClick={() => onSetCreateTarget({ kind: 'point', stage: 3 })}
          >
            + Пост
          </button>
          <div className="flex items-center gap-1">
            <select
              className="input text-xs py-1 min-h-0 w-14"
              value={mertvyakCreateSide}
              onChange={(e) => onMertvyakSideChange(e.target.value as 'A' | 'B')}
            >
              <option value="A">ЛК</option>
              <option value="B">СБГ</option>
            </select>
            <button
              type="button"
              className={`btn text-xs border py-1 min-h-0 ${
                createTarget?.kind === 'cache' && createTarget.cache_kind === 'mertvyak'
                  ? 'border-sideB bg-sideB/20 text-sideB'
                  : 'border-zinc-600'
              }`}
              onClick={() =>
                onSetCreateTarget({
                  kind: 'cache',
                  stage: 3,
                  cache_kind: 'mertvyak',
                  team_side: mertvyakCreateSide,
                })
              }
            >
              + Мертвяк
            </button>
          </div>
          <div className="flex items-center gap-1">
            <select
              className="input text-xs py-1 min-h-0"
              value={landmarkCreateKind}
              onChange={(e) => onLandmarkKindChange(e.target.value as 'base' | 'start' | 'base_start')}
            >
              <option value="base">База</option>
              <option value="start">Старт</option>
              <option value="base_start">База+старт</option>
            </select>
            <select
              className="input text-xs py-1 min-h-0 w-14"
              value={landmarkCreateSide}
              onChange={(e) => onLandmarkSideChange(e.target.value as 'A' | 'B')}
            >
              <option value="A">ЛК</option>
              <option value="B">СБГ</option>
            </select>
            <button
              type="button"
              className={`btn text-xs border py-1 min-h-0 ${
                createTarget?.kind === 'landmark' ? 'border-sideA bg-sideA/20 text-sideA' : 'border-zinc-600'
              }`}
              onClick={() =>
                onSetCreateTarget({
                  kind: 'landmark',
                  landmarkKind: landmarkCreateKind,
                  team_side: landmarkCreateSide,
                })
              }
            >
              + Ориентир
            </button>
          </div>
          {createTarget && (
            <button
              type="button"
              className="btn text-xs border border-zinc-600 py-1 min-h-0 text-zinc-400"
              onClick={() => onSetCreateTarget(null)}
            >
              Отмена
            </button>
          )}
        </div>
      )}
    </div>
  );
}
