import { useEffect, useState } from 'react';
import {
  fetchTowerAdminOverview,
  resetTowerUrZone,
  seedTowerScenario,
  setTowerCurrentPhase,
  updateTowerFaction,
  updateTowerPhases,
  updateTowerRevealSchedule,
  uploadTowerElderPhoto,
  type TowerAdminOverview,
} from '../../api/client';
function toLocalInputValue(iso: string): string {
  const d = new Date(iso);
  const pad = (n: number) => String(n).padStart(2, '0');
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(d.getMinutes())}`;
}

export default function TowerAdminPanel() {
  const [overview, setOverview] = useState<TowerAdminOverview | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [notes, setNotes] = useState<Record<number, string>>({});
  const [scheduleInputs, setScheduleInputs] = useState<string[]>(['']);
  const [copied, setCopied] = useState<string | null>(null);
  const [phaseInputs, setPhaseInputs] = useState<string[]>([]);
  const [uploadingPhoto, setUploadingPhoto] = useState<number | null>(null);

  const load = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await fetchTowerAdminOverview();
      setOverview(data);
      if (data) {
        setNotes(Object.fromEntries(data.factions.map((f) => [f.id, f.elder_note || ''])));
        setScheduleInputs(
          data.reveal_schedule.length ? data.reveal_schedule.map(toLocalInputValue) : ['']
        );
        setPhaseInputs(data.phases);
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка загрузки');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, []);

  const handleSeed = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await seedTowerScenario();
      setOverview(data);
      setNotes(Object.fromEntries(data.factions.map((f) => [f.id, f.elder_note || ''])));
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось создать сценарий');
    } finally {
      setLoading(false);
    }
  };

  const handleSaveNote = async (factionId: number) => {
    try {
      await updateTowerFaction(factionId, { elder_note: notes[factionId] || '' });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить');
    }
  };

  const handleResetZone = async (zoneId: number) => {
    try {
      await resetTowerUrZone(zoneId);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сбросить УР');
    }
  };

  const handleSaveSchedule = async () => {
    const thresholds = scheduleInputs
      .filter((s) => s.trim())
      .map((s) => new Date(s).toISOString())
      .sort();
    try {
      await updateTowerRevealSchedule(thresholds);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить расписание');
    }
  };

  const handleSavePhases = async () => {
    try {
      await updateTowerPhases(phaseInputs);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось сохранить этапы');
    }
  };

  const handleSetCurrentPhase = async (index: number) => {
    try {
      await setTowerCurrentPhase(index);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось переключить этап');
    }
  };

  const handleUploadPhoto = async (factionId: number, file: File) => {
    setUploadingPhoto(factionId);
    setError('');
    try {
      await uploadTowerElderPhoto(factionId, file);
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Не удалось загрузить фото');
    } finally {
      setUploadingPhoto(null);
    }
  };

  const copyLink = async (url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopied(url);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      /* буфер обмена недоступен — молча игнорируем */
    }
  };

  return (
    <div className="no-print p-4 space-y-5 border-t border-zinc-800 mt-2 pt-4">
      <div>
        <h2 className="text-base font-bold text-sideA">Башня — стороны, QR, укрепрайоны</h2>
        <p className="text-sm text-zinc-400 mt-0.5">
          Отдельный сценарий с 4 сторонами (СБГ / ДРГ / Првонек / Корбул). Активируйте его выше в
          «Мероприятия», когда он готов к игре.
        </p>
      </div>

      {error && <p className="text-sm text-sideB">{error}</p>}

      {!overview && !loading && (
        <button type="button" className="btn bg-sideA text-white text-sm" onClick={() => void handleSeed()}>
          Создать сценарий «Башня»
        </button>
      )}

      {loading && !overview && <p className="text-sm text-zinc-500">Загрузка…</p>}

      {overview && (
        <>
          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-zinc-200">Этапы игры</h3>
            <p className="text-xs text-zinc-500">
              Переключаются вручную мастером — текущий этап виден игрокам и командирам на их страницах.
            </p>
            <div className="space-y-1">
              {phaseInputs.map((val, i) => (
                <div key={i} className="flex items-center gap-2">
                  <span
                    className={`text-xs w-5 shrink-0 ${i === overview.current_phase ? 'text-sideA font-bold' : 'text-zinc-600'}`}
                  >
                    {i === overview.current_phase ? '●' : i + 1}
                  </span>
                  <input
                    className="input flex-1 text-sm py-1"
                    value={val}
                    onChange={(e) => setPhaseInputs((arr) => arr.map((v, j) => (j === i ? e.target.value : v)))}
                  />
                  <button
                    type="button"
                    className={`btn text-xs py-0.5 px-2 min-h-0 border ${
                      i === overview.current_phase ? 'border-sideA text-sideA' : 'border-zinc-600'
                    }`}
                    disabled={i === overview.current_phase}
                    onClick={() => void handleSetCurrentPhase(i)}
                  >
                    {i === overview.current_phase ? 'Текущий' : 'Сделать текущим'}
                  </button>
                  <button
                    type="button"
                    className="btn text-xs py-0.5 px-2 min-h-0 border border-zinc-600"
                    onClick={() => setPhaseInputs((arr) => arr.filter((_, j) => j !== i))}
                  >
                    ✕
                  </button>
                </div>
              ))}
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                className="btn text-xs border border-zinc-600"
                onClick={() => setPhaseInputs((arr) => [...arr, ''])}
              >
                + этап
              </button>
              <button type="button" className="btn text-xs bg-sideA text-white" onClick={() => void handleSavePhases()}>
                Сохранить список этапов
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-zinc-200">Ссылки регистрации и командиры</h3>
            {overview.factions.map((f) => {
              const cmd = overview.commanders.find((c) => c.faction_code === f.code);
              return (
                <div key={f.id} className="rounded-lg border border-zinc-700 bg-zinc-950 p-3 space-y-2">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-semibold text-zinc-100">
                      {f.name} <span className="text-xs text-zinc-500">({f.kind === 'village' ? 'деревня' : 'штаб'})</span>
                    </span>
                    <span className="text-xs text-zinc-500">зарегистрировано: {f.registered_count}</span>
                  </div>
                  {f.join_url && (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-zinc-500">Ссылка регистрации игроков:</span>
                      <code className="text-sideA break-all">{f.join_url}</code>
                      <button
                        type="button"
                        className="btn text-xs py-0.5 px-2 min-h-0 border border-zinc-600"
                        onClick={() => void copyLink(f.join_url!)}
                      >
                        {copied === f.join_url ? '✓' : 'Копировать'}
                      </button>
                    </div>
                  )}
                  {f.qr_url && (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-zinc-500">QR-табличка деревни:</span>
                      <code className="text-sideA break-all">{f.qr_url}</code>
                    </div>
                  )}
                  {cmd && (
                    <div className="text-xs text-zinc-400">
                      Командир: <span className="font-mono text-zinc-200">{cmd.username}</span> / пароль{' '}
                      <span className="font-mono text-zinc-200">{cmd.password}</span>
                    </div>
                  )}
                  {f.kind === 'village' && (
                    <div className="pt-1">
                      <label className="text-xs text-zinc-500 block mb-1">
                        Досье старейшины (фото/текст — выдаётся СБГ и ДРГ при скане QR деревни)
                      </label>
                      <textarea
                        className="input w-full text-sm min-h-[60px]"
                        value={notes[f.id] ?? ''}
                        onChange={(e) => setNotes((n) => ({ ...n, [f.id]: e.target.value }))}
                        placeholder="Имя старейшины, приметы, где искать…"
                      />
                      <button
                        type="button"
                        className="btn text-xs mt-1 border border-zinc-600"
                        onClick={() => void handleSaveNote(f.id)}
                      >
                        Сохранить
                      </button>
                      <div className="flex items-center gap-2 mt-2">
                        {f.elder_photo_url && (
                          <img src={f.elder_photo_url} alt="Старейшина" className="w-12 h-12 object-cover rounded border border-zinc-700" />
                        )}
                        <label className="btn text-xs border border-zinc-600 cursor-pointer">
                          {uploadingPhoto === f.id ? 'Загрузка…' : f.elder_photo_url ? 'Заменить фото' : 'Загрузить фото'}
                          <input
                            type="file"
                            accept="image/jpeg,image/png,image/webp"
                            className="hidden"
                            disabled={uploadingPhoto === f.id}
                            onChange={(e) => {
                              const file = e.target.files?.[0];
                              e.target.value = '';
                              if (file) void handleUploadPhoto(f.id, file);
                            }}
                          />
                        </label>
                      </div>
                    </div>
                  )}
                </div>
              );
            })}
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-zinc-200">
              Расписание раскрытия координат схронов (реальное время)
            </h3>
            <p className="text-xs text-zinc-500">
              Каждый порог открывает следующую по счёту координату схрона враждебной деревне.
              Обязательно проставьте с правильной датой игры (12–13 сентября).
            </p>
            {scheduleInputs.map((val, i) => (
              <div key={i} className="flex items-center gap-2">
                <input
                  type="datetime-local"
                  className="input text-sm py-1"
                  value={val}
                  onChange={(e) =>
                    setScheduleInputs((arr) => arr.map((v, j) => (j === i ? e.target.value : v)))
                  }
                />
                <button
                  type="button"
                  className="btn text-xs py-0.5 px-2 min-h-0 border border-zinc-600"
                  onClick={() => setScheduleInputs((arr) => arr.filter((_, j) => j !== i))}
                >
                  Удалить
                </button>
              </div>
            ))}
            <div className="flex gap-2">
              <button
                type="button"
                className="btn text-xs border border-zinc-600"
                onClick={() => setScheduleInputs((arr) => [...arr, ''])}
              >
                + порог
              </button>
              <button type="button" className="btn text-xs bg-sideA text-white" onClick={() => void handleSaveSchedule()}>
                Сохранить расписание
              </button>
            </div>
          </div>

          <div className="space-y-2">
            <h3 className="text-sm font-semibold text-zinc-200">Укрепрайоны (СБГ синхро-захват / ДРГ сброс)</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
              {overview.ur_zones.map((z) => (
                <div key={z.id} className="rounded-lg border border-zinc-700 bg-zinc-950 p-3 space-y-1">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-zinc-100">{z.name}</span>
                    <span
                      className={`text-xs uppercase tracking-wide ${
                        z.status === 'captured'
                          ? 'text-sideA'
                          : z.status === 'holding'
                            ? 'text-warning'
                            : 'text-zinc-500'
                      }`}
                    >
                      {z.status}
                    </span>
                  </div>
                  <div className="text-xs text-zinc-500">
                    {z.points.map((p) => `${p.name}${p.scanned ? '✓' : ''}`).join(' · ')}
                  </div>
                  <button
                    type="button"
                    className="btn text-xs mt-1 border border-sideB text-sideB"
                    onClick={() => void handleResetZone(z.id)}
                  >
                    Сбросить вручную
                  </button>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
