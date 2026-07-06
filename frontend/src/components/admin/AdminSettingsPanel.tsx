import { useEffect, useState, type ReactNode } from 'react';
import type { GameSettings, StatusData } from '../../api/client';

export interface SettingsDraft {
  a: number;
  b: number;
  captureRadius: number;
  disableCaptureDistance: boolean;
  stage1Recapturable: boolean;
  captureMinutes: number;
  holdPingMinutes: number;
  postHoldMinutes: number;
  postHoldPingMinutes: number;
  stage2IssueMinutes: number;
  stage2IssueMode: 'random' | 'sequential';
  stage1SlotMinutes: number;
  stage1HoldSlots: string;
  gpsAccuracyBonusMax: number;
  gpsMinAccuracyForCapture: number;
  gpsLatOffset: number;
  gpsLonOffset: number;
  calibrateTrueLat: string;
  calibrateTrueLon: string;
  calibrateMeasuredLat: string;
  calibrateMeasuredLon: string;
}

type SectionId = 'engineers' | 'stage1_capture' | 'stage1_schedule' | 'stage3' | 'stage2' | 'gps';

interface AdminSettingsPanelProps {
  data: StatusData;
  settings: GameSettings | null;
  settingsDraft: SettingsDraft;
  settingsSaving: boolean;
  hasFilmLoot: boolean;
  onDraftChange: (updater: (d: SettingsDraft) => SettingsDraft) => void;
  onSave: () => void;
  onDownloadEngineers: () => void | Promise<void>;
  onGpsCalibrate?: () => void | Promise<void>;
  /** 'sheet' — inside MobileSheet without height cap */
  embedded?: 'inline' | 'sheet';
}

function defaultSection(data: StatusData, hasFilmLoot: boolean): SectionId {
  if (data.current_stage === 1) return 'stage1_capture';
  if (data.current_stage === 3) return 'stage3';
  if (hasFilmLoot) return 'stage2';
  return 'engineers';
}

function AccordionSection({
  id,
  title,
  openSection,
  onToggle,
  children,
}: {
  id: SectionId;
  title: string;
  openSection: SectionId | null;
  onToggle: (id: SectionId) => void;
  children: ReactNode;
}) {
  const open = openSection === id;
  return (
    <div className="border border-zinc-800 rounded-lg overflow-hidden">
      <button
        type="button"
        className="w-full flex items-center justify-between gap-2 px-3 py-2 text-left text-sm font-bold text-zinc-300 bg-zinc-900/80 hover:bg-zinc-800/80 transition-colors"
        onClick={() => onToggle(id)}
        aria-expanded={open}
      >
        {title}
        <span className="text-zinc-500 text-xs font-normal">{open ? '▼' : '▶'}</span>
      </button>
      {open && <div className="px-3 py-3 border-t border-zinc-800 space-y-3">{children}</div>}
    </div>
  );
}

export default function AdminSettingsPanel({
  data,
  settings,
  settingsDraft,
  settingsSaving,
  hasFilmLoot,
  onDraftChange,
  onSave,
  onDownloadEngineers,
  onGpsCalibrate,
  embedded = 'inline',
}: AdminSettingsPanelProps) {
  const [openSection, setOpenSection] = useState<SectionId | null>(() =>
    defaultSection(data, hasFilmLoot),
  );

  useEffect(() => {
    setOpenSection(defaultSection(data, hasFilmLoot));
  }, [data.current_stage, hasFilmLoot]);

  const toggleSection = (id: SectionId) => {
    setOpenSection((prev) => (prev === id ? null : id));
  };

  return (
    <div
      className={`no-print flex flex-col bg-zinc-950/95 ${
        embedded === 'inline'
          ? 'shrink-0 border-b border-zinc-800 max-h-[min(52vh,440px)]'
          : 'min-h-0'
      }`}
    >
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        <AccordionSection
          id="engineers"
          title="Пул инженеров"
          openSection={openSection}
          onToggle={toggleSection}
        >
          <p className="text-xs text-zinc-500">
            Количество на сторону. Не привязаны к этапу или точке.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-zinc-400">
              ЛК (A)
              <input
                type="number"
                min={1}
                max={50}
                className="input block mt-1 w-20 min-h-0 py-1 text-sm"
                value={settingsDraft.a}
                onChange={(e) => onDraftChange((d) => ({ ...d, a: Number(e.target.value) }))}
              />
            </label>
            <label className="text-xs text-zinc-400">
              СБГ (B)
              <input
                type="number"
                min={1}
                max={50}
                className="input block mt-1 w-20 min-h-0 py-1 text-sm"
                value={settingsDraft.b}
                onChange={(e) => onDraftChange((d) => ({ ...d, b: Number(e.target.value) }))}
              />
            </label>
            {settings && (
              <span className="text-xs text-zinc-500">
                Сейчас: ЛК {settings.engineers_count_a}, СБГ {settings.engineers_count_b}
              </span>
            )}
          </div>
          <p className="text-xs text-zinc-500">
            Учётки eng_a1…N / eng_b1…N. Для каждого инженера генерируется свой пароль из 6 символов
            (буквы и цифры). eng_a1 и eng_b1 — тестовые с фиксированными паролями alfa01 / bravo1.
            Остальные — после «Применить настройки» скачайте список и раздайте пароли.
          </p>
          <button
            type="button"
            className="btn text-sm border border-zinc-600"
            onClick={() => void onDownloadEngineers()}
          >
            Скачать список (CSV)
          </button>
        </AccordionSection>

        <AccordionSection
          id="stage1_capture"
          title="Этап 1 · захват КТ"
          openSection={openSection}
          onToggle={toggleSection}
        >
          <p className="text-xs text-zinc-500">
            Стороны начинают на точках старта. Захват КТ по слотам — слот запускается вручную из штаба.
            Радиус в метрах, время захвата КТ и интервал кнопки «Подтвердить удержание».
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-zinc-400">
              Радиус захвата, м
              <input
                type="number"
                min={1}
                max={500}
                className="input block mt-1 w-24 min-h-0 py-1 text-sm"
                value={settingsDraft.captureRadius}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, captureRadius: Number(e.target.value) }))
                }
              />
            </label>
            <label className="text-xs text-zinc-400">
              Время захвата КТ, мин
              <input
                type="number"
                min={1}
                max={60}
                className="input block mt-1 w-24 min-h-0 py-1 text-sm"
                value={settingsDraft.captureMinutes}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, captureMinutes: Number(e.target.value) }))
                }
              />
            </label>
            <label className="text-xs text-zinc-400">
              Интервал кнопки, мин
              <input
                type="number"
                min={1}
                max={60}
                className="input block mt-1 w-24 min-h-0 py-1 text-sm"
                value={settingsDraft.holdPingMinutes}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, holdPingMinutes: Number(e.target.value) }))
                }
              />
            </label>
            <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer select-none pb-1">
              <input
                type="checkbox"
                className="rounded border-zinc-600"
                checked={settingsDraft.disableCaptureDistance}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, disableCaptureDistance: e.target.checked }))
                }
              />
              Отключить проверку дистанции (тест)
            </label>
            <label className="flex items-center gap-2 text-xs text-zinc-400 cursor-pointer select-none pb-1">
              <input
                type="checkbox"
                className="rounded border-zinc-600"
                checked={settingsDraft.stage1Recapturable}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, stage1Recapturable: e.target.checked }))
                }
              />
              Перезахватываемые КТ
            </label>
          </div>
          {settings && (
            <p className="text-xs text-zinc-500">
              Сейчас: радиус {settings.capture_radius_m}м · захват{' '}
              {Math.round(settings.point_capture_seconds / 60)} мин · кнопка{' '}
              {Math.round(settings.point_hold_ping_seconds / 60)} мин
              {settings.disable_capture_distance ? ' · тест: без геозоны' : ''}
              {settings.stage1_recapturable === false ? ' · без перезахвата' : ''}
            </p>
          )}
        </AccordionSection>

        <AccordionSection
          id="gps"
          title="GPS и геозона"
          openSection={openSection}
          onToggle={toggleSection}
        >
          <p className="text-xs text-zinc-500">
            Бонус к радиусу захвата по погрешности GPS. Минимальная точность для кнопки захвата: 0 = не
            проверять. Смещение координат применяется ко всем GPS-фиксам инженеров. Точки и ящики можно
            подвинуть на карте в режиме редактирования.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-zinc-400">
              Бонус accuracy, м (макс)
              <input
                type="number"
                min={0}
                max={100}
                className="input block mt-1 w-24 min-h-0 py-1 text-sm"
                value={settingsDraft.gpsAccuracyBonusMax}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, gpsAccuracyBonusMax: Number(e.target.value) }))
                }
              />
            </label>
            <label className="text-xs text-zinc-400">
              Мин. точность для захвата, м
              <input
                type="number"
                min={0}
                max={200}
                className="input block mt-1 w-24 min-h-0 py-1 text-sm"
                value={settingsDraft.gpsMinAccuracyForCapture}
                onChange={(e) =>
                  onDraftChange((d) => ({
                    ...d,
                    gpsMinAccuracyForCapture: Number(e.target.value),
                  }))
                }
              />
            </label>
            <label className="text-xs text-zinc-400">
              Смещение lat
              <input
                type="number"
                step="0.000001"
                className="input block mt-1 w-32 min-h-0 py-1 text-sm font-mono"
                value={settingsDraft.gpsLatOffset}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, gpsLatOffset: Number(e.target.value) }))
                }
              />
            </label>
            <label className="text-xs text-zinc-400">
              Смещение lon
              <input
                type="number"
                step="0.000001"
                className="input block mt-1 w-32 min-h-0 py-1 text-sm font-mono"
                value={settingsDraft.gpsLonOffset}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, gpsLonOffset: Number(e.target.value) }))
                }
              />
            </label>
          </div>
          <div className="border border-zinc-800 rounded-lg p-3 space-y-2">
            <p className="text-xs text-zinc-400 font-medium">Калибровка по известной точке</p>
            <p className="text-xs text-zinc-500">
              Встаньте на КТ/базу с телефона, запишите GPS с экрана инженера. Введите реальные координаты
              точки — система посчитает смещение.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <label className="text-xs text-zinc-400">
                Реальная широта
                <input
                  className="input block mt-1 w-full min-h-0 py-1 text-sm font-mono"
                  value={settingsDraft.calibrateTrueLat}
                  onChange={(e) =>
                    onDraftChange((d) => ({ ...d, calibrateTrueLat: e.target.value }))
                  }
                />
              </label>
              <label className="text-xs text-zinc-400">
                Реальная долгота
                <input
                  className="input block mt-1 w-full min-h-0 py-1 text-sm font-mono"
                  value={settingsDraft.calibrateTrueLon}
                  onChange={(e) =>
                    onDraftChange((d) => ({ ...d, calibrateTrueLon: e.target.value }))
                  }
                />
              </label>
              <label className="text-xs text-zinc-400">
                GPS широта (с телефона)
                <input
                  className="input block mt-1 w-full min-h-0 py-1 text-sm font-mono"
                  value={settingsDraft.calibrateMeasuredLat}
                  onChange={(e) =>
                    onDraftChange((d) => ({ ...d, calibrateMeasuredLat: e.target.value }))
                  }
                />
              </label>
              <label className="text-xs text-zinc-400">
                GPS долгота (с телефона)
                <input
                  className="input block mt-1 w-full min-h-0 py-1 text-sm font-mono"
                  value={settingsDraft.calibrateMeasuredLon}
                  onChange={(e) =>
                    onDraftChange((d) => ({ ...d, calibrateMeasuredLon: e.target.value }))
                  }
                />
              </label>
            </div>
            {onGpsCalibrate && (
              <button
                type="button"
                className="btn text-sm border border-zinc-600 text-zinc-300 min-h-0 py-1.5 px-3"
                onClick={() => void onGpsCalibrate()}
                disabled={settingsSaving}
              >
                Записать смещение
              </button>
            )}
          </div>
          {settings && (
            <p className="text-xs text-zinc-500">
              Сейчас: бонус ≤{settings.gps_accuracy_bonus_max_m}м
              {settings.gps_min_accuracy_for_capture_m > 0
                ? ` · захват при accuracy ≤${settings.gps_min_accuracy_for_capture_m}м`
                : ''}
              {(settings.gps_lat_offset !== 0 || settings.gps_lon_offset !== 0)
                ? ` · смещение ${settings.gps_lat_offset.toFixed(6)}, ${settings.gps_lon_offset.toFixed(6)}`
                : ''}
            </p>
          )}
        </AccordionSection>

        <AccordionSection
          id="stage1_schedule"
          title="Этап 1 · слоты КТ"
          openSection={openSection}
          onToggle={toggleSection}
        >
          <p className="text-xs text-zinc-500">
            Первый слот запускается вручную из штаба. Следующие слоты переключаются автоматически по таймеру.
          </p>
          <label className="text-xs text-zinc-400 inline-block">
            Слот, мин
            <input
              type="number"
              min={1}
              max={1440}
              className="input block mt-1 w-24 min-h-0 py-1 text-sm"
              value={settingsDraft.stage1SlotMinutes}
              onChange={(e) =>
                onDraftChange((d) => ({ ...d, stage1SlotMinutes: Number(e.target.value) }))
              }
            />
          </label>
          <label className="block text-xs text-zinc-400 mt-3">
            Наборы КТ по слотам (строка = слот, номера через запятую)
            <textarea
              className="input w-full mt-1 text-sm py-1.5 min-h-[4.5rem] font-mono resize-y"
              rows={3}
              value={settingsDraft.stage1HoldSlots}
              onChange={(e) => onDraftChange((d) => ({ ...d, stage1HoldSlots: e.target.value }))}
            />
          </label>
        </AccordionSection>

        <AccordionSection
          id="stage3"
          title="Этап 3 · удержание поста"
          openSection={openSection}
          onToggle={toggleSection}
        >
          <p className="text-xs text-zinc-500">
            Время удержания перед подрывом и интервал кнопки подтверждения для инженера.
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-zinc-400">
              Время удержания, мин
              <input
                type="number"
                min={1}
                max={120}
                className="input block mt-1 w-24 min-h-0 py-1 text-sm"
                value={settingsDraft.postHoldMinutes}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, postHoldMinutes: Number(e.target.value) }))
                }
              />
            </label>
            <label className="text-xs text-zinc-400">
              Интервал кнопки, мин
              <input
                type="number"
                min={1}
                max={60}
                className="input block mt-1 w-24 min-h-0 py-1 text-sm"
                value={settingsDraft.postHoldPingMinutes}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, postHoldPingMinutes: Number(e.target.value) }))
                }
              />
            </label>
          </div>
          {settings && (
            <p className="text-xs text-zinc-500">
              Сейчас: удержание {Math.round(settings.post_hold_seconds / 60)} мин · кнопка{' '}
              {Math.round(settings.post_hold_ping_seconds / 60)} мин
            </p>
          )}
        </AccordionSection>

        <AccordionSection
          id="stage2"
          title="Задача-2 · автовыдача"
          openSection={openSection}
          onToggle={toggleSection}
        >
          <p className="text-xs text-zinc-500">
            Автовыдача по интервалу — только после включения Задачи-2. Включение и выдача цели — в панели
            «Ящики и коды».
          </p>
          <div className="flex flex-wrap items-end gap-3">
            <label className="text-xs text-zinc-400">
              Интервал автовыдачи, мин
              <input
                type="number"
                min={1}
                max={1440}
                className="input block mt-1 w-24 min-h-0 py-1 text-sm"
                value={settingsDraft.stage2IssueMinutes}
                onChange={(e) =>
                  onDraftChange((d) => ({ ...d, stage2IssueMinutes: Number(e.target.value) }))
                }
              />
            </label>
            <label className="text-xs text-zinc-400">
              Режим
              <select
                className="input block mt-1 min-h-0 py-1 text-sm"
                value={settingsDraft.stage2IssueMode}
                onChange={(e) =>
                  onDraftChange((d) => ({
                    ...d,
                    stage2IssueMode: e.target.value as 'random' | 'sequential',
                  }))
                }
              >
                <option value="random">Случайный</option>
                <option value="sequential">По порядку</option>
              </select>
            </label>
          </div>
          {settings && (
            <p className="text-xs text-zinc-500">
              Сейчас: {settings.stage2_issue_interval_minutes} мин ·{' '}
              {settings.stage2_issue_mode === 'sequential' ? 'по порядку' : 'случайно'}
            </p>
          )}
        </AccordionSection>
      </div>

      <div className="shrink-0 sticky bottom-0 border-t border-zinc-800 bg-zinc-950/95 p-3">
        <button
          type="button"
          className="btn bg-sideA text-white text-sm w-full sm:w-auto disabled:opacity-50"
          disabled={settingsSaving}
          onClick={onSave}
        >
          {settingsSaving ? '…' : 'Применить настройки'}
        </button>
      </div>
    </div>
  );
}
