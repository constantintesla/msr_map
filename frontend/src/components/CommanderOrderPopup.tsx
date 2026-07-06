import { useState } from 'react';
import { sendFieldOrder, type EngineerPoolItem, type StatusData } from '../api/client';
import PointPopupExtras from './PointPopupExtras';

interface Target {
  id: number;
  name: string;
  lat: number;
  lon: number;
}

interface CommanderOrderPopupProps {
  targetKind: 'point' | 'cache';
  target: Target;
  engineers: EngineerPoolItem[];
  pointData?: StatusData['points'][number];
  stage1Phase?: string | null;
  side?: string;
  onClose: () => void;
  onSent: () => void;
  onPhotoUploaded?: () => void;
}

export default function CommanderOrderPopup({
  targetKind,
  target,
  engineers,
  pointData,
  stage1Phase,
  side = 'A',
  onClose,
  onSent,
  onPhotoUploaded,
}: CommanderOrderPopupProps) {
  const [engineerId, setEngineerId] = useState(engineers[0]?.id ?? 0);
  const [note, setNote] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);

  const handleSend = async () => {
    if (!engineerId) {
      setError('Выберите инженера');
      return;
    }
    setSending(true);
    setError('');
    try {
      await sendFieldOrder({
        engineer_user_id: engineerId,
        target_kind: targetKind,
        target_id: target.id,
        note: note.trim() || undefined,
      });
      setDone(true);
      setTimeout(onSent, 600);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Ошибка отправки');
    } finally {
      setSending(false);
    }
  };

  const kindLabel = targetKind === 'point' ? 'Точка' : 'Схрон';

  return (
    <div className="admin-popup text-sm space-y-3 min-w-[240px]">
      <div>
        <p className="text-[10px] uppercase tracking-wide text-zinc-500">{kindLabel}</p>
        <p className="font-bold text-zinc-100">{target.name}</p>
        <p className="text-xs text-zinc-500 font-mono mt-0.5">
          {target.lat.toFixed(5)}, {target.lon.toFixed(5)}
        </p>
      </div>

      {pointData && <PointPopupExtras point={pointData} stage1Phase={stage1Phase} />}

      {done ? (
        <p className="text-green-400 text-xs">Приказ отправлен</p>
      ) : (
        <>
          <label className="block text-xs text-zinc-400">
            Инженер
            <select
              className="input w-full mt-1 min-h-0 py-1.5 text-sm"
              value={engineerId}
              onChange={(e) => setEngineerId(Number(e.target.value))}
            >
              {engineers.length === 0 && <option value={0}>Нет инженеров</option>}
              {engineers.map((eng) => (
                <option key={eng.id} value={eng.id}>
                  {eng.username}
                  {eng.lpd_channel ? ` · LPD ${eng.lpd_channel}` : ''}
                </option>
              ))}
            </select>
          </label>

          <label className="block text-xs text-zinc-400">
            Комментарий (необязательно)
            <textarea
              className="input w-full mt-1 text-sm py-1.5 min-h-[3rem] resize-none"
              rows={2}
              placeholder="Напр.: разведка, подготовка к захвату…"
              value={note}
              onChange={(e) => setNote(e.target.value)}
            />
          </label>

          {error && <p className="text-xs text-sideB">{error}</p>}

          <div className="flex gap-2">
            <button
              type="button"
              className="btn flex-1 bg-sideA text-white text-sm min-h-0 py-2 disabled:opacity-50"
              disabled={sending || engineers.length === 0}
              onClick={() => void handleSend()}
            >
              {sending ? '…' : 'Отправить приказ'}
            </button>
            <button type="button" className="btn border border-zinc-700 text-sm min-h-0 py-2" onClick={onClose}>
              Отмена
            </button>
          </div>
        </>
      )}
    </div>
  );
}
