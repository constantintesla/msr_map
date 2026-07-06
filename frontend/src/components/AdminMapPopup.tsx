import type { StatusData } from '../api/client';
import PointPopupExtras from './PointPopupExtras';

interface MissionBox {
  id: number;
  name: string;
  lat: number;
  lon: number;
  code: string;
  url: string;
}

interface AdminMapPopupProps {
  point?: StatusData['points'][number];
  cache?: StatusData['caches'][number];
  landmark?: NonNullable<StatusData['landmarks']>[number];
  currentStage: number;
  mission?: MissionBox | null;
  editCode?: string;
  onEditCode?: (value: string) => void;
  onSaveCode?: () => void;
  codeSaving?: boolean;
  onForceRelease?: (pointId: number) => void;
  onDownloadPdf?: () => void;
  onAdminConfirm?: (cacheId: number) => void;
  onAdminConfirmManual?: (cacheId: number, side: 'A' | 'B') => void;
  onAdminConfirmDelivery?: (cacheId: number) => void;
  onAdminConfirmDeliveryManual?: (cacheId: number, side: 'A' | 'B') => void;
  onAdminConfirmPoint?: (pointId: number) => void;
  stage1Phase?: string | null;
  onPhotoUploaded?: () => void;
  mapEditMode?: boolean;
  editName?: string;
  onEditName?: (value: string) => void;
  onSaveName?: () => void;
  nameSaving?: boolean;
  onDelete?: () => void;
}

function MapEditBlock({
  editName = '',
  onEditName,
  onSaveName,
  nameSaving,
  onDelete,
}: Pick<AdminMapPopupProps, 'editName' | 'onEditName' | 'onSaveName' | 'nameSaving' | 'onDelete'>) {
  if (!onEditName || !onSaveName || !onDelete) return null;
  return (
    <div className="border-t border-zinc-700 pt-2 space-y-2">
      <div className="text-xs text-zinc-400">Редактирование карты</div>
      <input
        className="input w-full text-sm py-1 min-h-0"
        value={editName}
        onChange={(e) => onEditName(e.target.value)}
      />
      <div className="flex gap-2">
        <button
          type="button"
          className="btn flex-1 text-xs border border-zinc-600 py-1 min-h-0"
          disabled={nameSaving}
          onClick={() => onSaveName()}
        >
          {nameSaving ? '…' : 'Сохранить имя'}
        </button>
        <button
          type="button"
          className="btn flex-1 text-xs border border-sideB text-sideB py-1 min-h-0"
          disabled={nameSaving}
          onClick={() => onDelete()}
        >
          Удалить
        </button>
      </div>
    </div>
  );
}

export default function AdminMapPopup({
  point,
  cache,
  landmark,
  currentStage,
  mission,
  editCode = '',
  onEditCode,
  onSaveCode,
  codeSaving,
  onForceRelease,
  onDownloadPdf,
  onAdminConfirm,
  onAdminConfirmManual,
  onAdminConfirmDelivery,
  onAdminConfirmDeliveryManual,
  onAdminConfirmPoint,
  stage1Phase,
  onPhotoUploaded,
  mapEditMode,
  editName,
  onEditName,
  onSaveName,
  nameSaving,
  onDelete,
}: AdminMapPopupProps) {
  const mapEditBlock = mapEditMode ? (
    <MapEditBlock
      editName={editName}
      onEditName={onEditName}
      onSaveName={onSaveName}
      nameSaving={nameSaving}
      onDelete={onDelete}
    />
  ) : null;

  if (landmark) {
    const kindLabel =
      landmark.kind === 'base_start' ? 'База + старт' : landmark.kind === 'base' ? 'База' : 'Старт';
    return (
      <div className="admin-popup text-sm space-y-2">
        <div className="font-bold text-base">{landmark.name}</div>
        <div className="text-zinc-400">
          {kindLabel} · {landmark.team_side === 'A' ? 'ЛК' : 'СБГ'}
        </div>
        <div className="font-mono text-xs text-zinc-500">
          {landmark.lat.toFixed(6)}, {landmark.lon.toFixed(6)}
        </div>
        {mapEditBlock}
      </div>
    );
  }

  if (point) {
    const isPost = currentStage === 3;
    return (
      <div className="admin-popup text-sm space-y-2">
        <div className="font-bold text-base">{point.name}</div>
        <div className="text-zinc-400">{isPost ? 'Пост этапа 3' : `КТ #${point.id}`}</div>
        <div className="font-mono text-xs text-zinc-500">
          {point.lat.toFixed(6)}, {point.lon.toFixed(6)}
        </div>
        {!isPost && (
          <div>
            Сторона:{' '}
            <span className={point.side === 'A' ? 'text-sideA' : point.side === 'B' ? 'text-sideB' : ''}>
              {point.side || 'нейтральная'}
            </span>
          </div>
        )}
        {!point.destroyed && (
          <div>
            {isPost ? 'Удержание' : 'Захват'}:{' '}
            {point.held_by ? (
              <span className={point.held_by === 'A' ? 'text-sideA font-bold' : 'text-sideB font-bold'}>
                сторона {point.held_by}
                {isPost && point.hold_ready && <span className="text-green-400"> · готово к видео ОК</span>}
                {isPost && point.held_by && !point.hold_ready && (
                  <span className="text-zinc-500">
                    {' '}
                    · {Math.floor((point.hold_elapsed_sec || 0) / 60)}/10 мин
                  </span>
                )}
                {!isPost && point.held_by && !point.hold_ready && (
                  <span className="text-zinc-500">
                    {' '}
                    · захват {Math.floor((point.hold_elapsed_sec || 0) / 60)} мин
                  </span>
                )}
                {!isPost && point.hold_ready && <span className="text-green-400"> · захвачена</span>}
              </span>
            ) : (
              <span className="text-zinc-500">{isPost ? 'не удерживается' : 'свободна'}</span>
            )}
          </div>
        )}
        {isPost && (
          <div>
            Статус:{' '}
            {point.pending_admin ? (
              <span className="text-warning">подорван, видео в чате, ждёт штаба</span>
            ) : point.destroyed && point.admin_confirmed ? (
              <span className="text-zinc-500">выключен штабом</span>
            ) : point.destroyed ? (
              <span className="text-sideB">подорван ({point.destroyed_by_side})</span>
            ) : (
              <span className="text-green-400">активен</span>
            )}
          </div>
        )}
        {point.hold_started_at && !point.destroyed && (
          <div className="text-xs text-zinc-500">
            С: {new Date(point.hold_started_at).toLocaleTimeString()}
          </div>
        )}
        {currentStage === 1 && (
          <PointPopupExtras point={point} stage1Phase={stage1Phase} />
        )}
        {currentStage === 1 && mission && (
          <>
            <div className="flex items-center gap-2">
              <span className="text-zinc-400">Код:</span>
              <input
                className="input w-20 text-center font-mono text-base py-1 min-h-0"
                inputMode="numeric"
                maxLength={6}
                value={editCode}
                onChange={(e) => onEditCode?.(e.target.value.replace(/\D/g, ''))}
              />
              <button
                type="button"
                className="btn text-xs border border-zinc-600 py-1 min-h-0 px-2"
                disabled={codeSaving}
                onClick={onSaveCode}
              >
                {codeSaving ? '…' : 'OK'}
              </button>
            </div>
            <a href={mission.url} target="_blank" rel="noreferrer" className="text-sideA underline text-xs block">
              {mission.url}
            </a>
            {onDownloadPdf && (
              <button
                type="button"
                className="btn w-full text-xs border border-warning text-warning py-1 min-h-0"
                onClick={onDownloadPdf}
              >
                PDF таблички (1 лист)
              </button>
            )}
          </>
        )}
        {isPost && point.pending_admin && onAdminConfirmPoint && (
          <button
            type="button"
            className="btn w-full text-xs bg-green-600 text-white py-2 min-h-0 mt-1"
            onClick={() => onAdminConfirmPoint(point.id)}
          >
            Подтвердить пост (видео в ТГ)
          </button>
        )}
        {!isPost && point.held_by && onForceRelease && (
          <button
            type="button"
            className="btn w-full text-xs bg-sideB text-white py-1 min-h-0 mt-1"
            onClick={() => onForceRelease(point.id)}
          >
            Сбросить захват
          </button>
        )}
        {mapEditBlock}
      </div>
    );
  }

  if (!cache) return null;

  const isFilmLoot = cache.cache_kind === 'film_loot';
  const isMertvyak = cache.cache_kind === 'mertvyak';

  return (
    <div className="admin-popup text-sm space-y-2">
      <div className="font-bold text-base">{cache.name}</div>
      <div className="text-zinc-400">
        {isFilmLoot ? 'Ящик за плёнкой' : isMertvyak ? 'Мертвяк' : 'Схрон'} #{cache.id}
      </div>
      <div className="font-mono text-xs text-zinc-500">
        {cache.lat.toFixed(6)}, {cache.lon.toFixed(6)}
      </div>

      {isMertvyak && currentStage === 3 && mission && (
        <>
          <div className="flex items-center gap-2">
            <span className="text-zinc-400">Код:</span>
            <input
              className="input w-20 text-center font-mono text-base py-1 min-h-0"
              inputMode="numeric"
              maxLength={6}
              value={editCode}
              onChange={(e) => onEditCode?.(e.target.value.replace(/\D/g, ''))}
            />
            <button
              type="button"
              className="btn text-xs border border-zinc-600 py-1 min-h-0 px-2"
              disabled={codeSaving}
              onClick={onSaveCode}
            >
              {codeSaving ? '…' : 'OK'}
            </button>
          </div>
        </>
      )}

      {isFilmLoot && currentStage === 2 && mission && (
        <>
          <div className="flex items-center gap-2">
            <span className="text-zinc-400">Код:</span>
            <input
              className="input w-20 text-center font-mono text-base py-1 min-h-0"
              inputMode="numeric"
              maxLength={6}
              value={editCode}
              onChange={(e) => onEditCode?.(e.target.value.replace(/\D/g, ''))}
            />
            <button
              type="button"
              className="btn text-xs border border-zinc-600 py-1 min-h-0 px-2"
              disabled={codeSaving}
              onClick={onSaveCode}
            >
              {codeSaving ? '…' : 'OK'}
            </button>
          </div>
          <a href={mission.url} target="_blank" rel="noreferrer" className="text-sideA underline text-xs block">
            {mission.url}
          </a>
          {onDownloadPdf && (
            <button
              type="button"
              className="btn w-full text-xs border border-warning text-warning py-1 min-h-0"
              onClick={onDownloadPdf}
            >
              PDF для наклейки (1 лист)
            </button>
          )}
        </>
      )}

      {isFilmLoot && (
        <div className="space-y-1 text-xs">
          <div>
            Плёнка:{' '}
            {cache.pending_admin ? (
              <span className="text-warning">видеоотчёт, ждёт штаба</span>
            ) : cache.destroyed && cache.admin_confirmed ? (
              <span className="text-zinc-500">подтверждена админом ({cache.destroyed_by_side})</span>
            ) : cache.destroyed ? (
              <span className="text-purple-400">вскрыта ({cache.destroyed_by_side})</span>
            ) : (
              <span className="text-warning">цела</span>
            )}
          </div>
          <div>
            Доставка:{' '}
            {cache.pending_delivery_admin ? (
              <span className="text-warning">фото с базы, ждёт штаба</span>
            ) : cache.delivered ? (
              <span className="text-green-400">подтверждена ({cache.delivered_by_side})</span>
            ) : cache.delivery_reported ? (
              <span className="text-purple-400">фото отправлено ({cache.delivered_by_side})</span>
            ) : (
              <span className="text-zinc-500">нет</span>
            )}
          </div>
          {cache.pending_admin && (
            <p className="text-[10px] text-zinc-500">
              Видео: Чат → Командование ({cache.destroyed_by_side === 'A' ? 'ЛК' : 'СБГ'})
            </p>
          )}
          {cache.pending_delivery_admin && (
            <p className="text-[10px] text-zinc-500">
              Фото: Чат → Командование ({cache.delivered_by_side === 'A' ? 'ЛК' : 'СБГ'})
            </p>
          )}
          {cache.pending_admin && onAdminConfirm && (
            <button
              type="button"
              className="btn w-full text-xs bg-green-600 text-white py-2 min-h-0 mt-1"
              onClick={() => onAdminConfirm(cache.id)}
            >
              Подтвердить видеоотчёт
            </button>
          )}
          {cache.pending_delivery_admin && onAdminConfirmDelivery && (
            <button
              type="button"
              className="btn w-full text-xs bg-green-600 text-white py-2 min-h-0 mt-1"
              onClick={() => onAdminConfirmDelivery(cache.id)}
            >
              Подтвердить доставку
            </button>
          )}
          {!cache.destroyed && !cache.admin_confirmed && onAdminConfirmManual && (
            <div className="space-y-1 pt-1 border-t border-zinc-800">
              <p className="text-[10px] text-zinc-500">
                Без видео в системе (например, отчёт в Telegram) — подтверждает только админ:
              </p>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="btn flex-1 text-xs bg-sideA text-white py-2 min-h-0"
                  onClick={() => onAdminConfirmManual(cache.id, 'A')}
                >
                  Вскрыла ЛК
                </button>
                <button
                  type="button"
                  className="btn flex-1 text-xs bg-sideB text-white py-2 min-h-0"
                  onClick={() => onAdminConfirmManual(cache.id, 'B')}
                >
                  Вскрыла СБГ
                </button>
              </div>
            </div>
          )}
          {cache.destroyed &&
            !cache.delivered &&
            !cache.delivery_reported &&
            onAdminConfirmDeliveryManual && (
            <div className="space-y-1 pt-1 border-t border-zinc-800">
              <p className="text-[10px] text-zinc-500">
                Без фото в системе (например, отчёт в Telegram) — подтверждает только админ:
              </p>
              <div className="flex gap-1">
                <button
                  type="button"
                  className="btn flex-1 text-xs bg-sideA text-white py-2 min-h-0"
                  onClick={() => onAdminConfirmDeliveryManual(cache.id, 'A')}
                >
                  Сдала ЛК
                </button>
                <button
                  type="button"
                  className="btn flex-1 text-xs bg-sideB text-white py-2 min-h-0"
                  onClick={() => onAdminConfirmDeliveryManual(cache.id, 'B')}
                >
                  Сдала СБГ
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {!isFilmLoot && (
        <>
          <div>
            Сторона:{' '}
            <span className={cache.team_side === 'A' ? 'text-sideA' : 'text-sideB'}>
              {cache.team_side === 'A' ? 'ЛК' : cache.team_side === 'B' ? 'СБГ' : '—'}
            </span>
          </div>
          {isMertvyak && (
            <div>
              В игре:{' '}
              {cache.enabled !== false ? (
                <span className="text-green-400">включён</span>
              ) : (
                <span className="text-zinc-500">выключен</span>
              )}
            </div>
          )}
          {!isMertvyak && (
            <div>
              Статус:{' '}
              {cache.pending_admin ? (
                <span className="text-warning">подорван, ждёт видео в ТГ</span>
              ) : cache.destroyed && cache.admin_confirmed ? (
                <span className="text-zinc-500">выключен штабом</span>
              ) : cache.destroyed ? (
                <span className="text-sideB">подорван ({cache.destroyed_by_side})</span>
              ) : (
                <span className="text-green-400">активен</span>
              )}
            </div>
          )}
          {cache.pending_admin && onAdminConfirm && (
            <button
              type="button"
              className="btn w-full text-xs bg-green-600 text-white py-2 min-h-0 mt-1"
              onClick={() => onAdminConfirm(cache.id)}
            >
              Подтвердить (видео в ТГ)
            </button>
          )}
        </>
      )}
      {mapEditBlock}
    </div>
  );
}
