import { useCallback, useEffect, useState } from 'react';
import {
  fetchAdminFieldOrders,
  fetchCommanderFieldOrders,
  type FieldOrder,
} from '../api/client';

interface FieldOrdersPanelProps {
  mode: 'admin' | 'commander';
  side?: 'A' | 'B';
  refreshToken?: number;
}

export default function FieldOrdersPanel({ mode, side = 'A', refreshToken = 0 }: FieldOrdersPanelProps) {
  const [orders, setOrders] = useState<FieldOrder[]>([]);

  const load = useCallback(() => {
    const req =
      mode === 'admin' ? fetchAdminFieldOrders(side) : fetchCommanderFieldOrders();
    req.then(setOrders).catch(() => {});
  }, [mode, side]);

  useEffect(() => {
    load();
  }, [load, refreshToken]);

  useEffect(() => {
    const id = setInterval(load, 20000);
    return () => clearInterval(id);
  }, [load]);

  if (orders.length === 0) {
    return (
      <div className="px-3 py-2 border-b border-zinc-800 text-xs text-zinc-600">
        Приказы инженерам — пока нет
      </div>
    );
  }

  return (
    <div className="shrink-0 border-b border-zinc-800 max-h-40 overflow-y-auto">
      <p className="px-3 pt-2 pb-1 text-[10px] uppercase tracking-wide text-zinc-500 font-bold">
        Приказы инженерам
      </p>
      <ul className="px-2 pb-2 space-y-1">
        {orders.slice(0, 15).map((o) => (
          <li
            key={o.id}
            className="rounded-lg border border-zinc-800 bg-zinc-900/50 px-2 py-1.5 text-xs"
          >
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <span className="font-mono text-zinc-300">{o.engineer_username}</span>
                <span className="text-zinc-600 mx-1">→</span>
                <span className="text-zinc-400">{o.target_name}</span>
              </div>
              {o.acknowledged_at || o.dismissed ? (
                <span className="shrink-0 text-green-400 font-medium" title="Подтверждено">
                  ✓
                </span>
              ) : (
                <span className="shrink-0 text-warning" title="Ожидает">
                  …
                </span>
              )}
            </div>
            <p className="text-[10px] text-zinc-600 mt-0.5">
              {new Date(o.created_at).toLocaleTimeString()}
              {mode === 'admin' && (
                <span className="ml-1.5">{o.side === 'A' ? 'ЛК' : 'СБГ'}</span>
              )}
              {(o.acknowledged_at || o.dismissed) && (
                <span className="ml-1.5 text-green-500/80">
                  принято {new Date(o.acknowledged_at!).toLocaleTimeString()}
                </span>
              )}
            </p>
          </li>
        ))}
      </ul>
    </div>
  );
}
