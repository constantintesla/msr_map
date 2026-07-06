import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useLocation } from 'react-router-dom';
import {
  dismissFieldOrder,
  fetchActiveFieldOrders,
  type FieldOrder,
} from '../api/client';
import { engineerSocketHub } from '../ws/hubs';

interface EngineerOrdersContextValue {
  orders: FieldOrder[];
  latest: FieldOrder | null;
  dismiss: (orderId: number) => Promise<void>;
  reload: () => void;
}

const EngineerOrdersContext = createContext<EngineerOrdersContextValue | null>(null);

export function EngineerOrdersProvider({ children }: { children: ReactNode }) {
  // Перечитать role/username после login → navigate (родитель иначе не ре-рендерится)
  useLocation();
  const [orders, setOrders] = useState<FieldOrder[]>([]);
  const isEngineer = localStorage.getItem('role') === 'engineer';
  const username = localStorage.getItem('username') || '';

  const load = useCallback(() => {
    if (!isEngineer) return;
    fetchActiveFieldOrders()
      .then(setOrders)
      .catch(() => {});
  }, [isEngineer]);

  const dismiss = useCallback(async (orderId: number) => {
    await dismissFieldOrder(orderId);
    setOrders((prev) => prev.filter((o) => o.id !== orderId));
  }, []);

  useEffect(() => {
    if (!isEngineer) return;

    load();
    const pollId = setInterval(load, 45000);

    const unsub = engineerSocketHub.subscribe((packet) => {
      if (packet.e === 'field_order' && packet.u === username) {
        load();
        return;
      }
      if (packet.e === 'field_order_update') {
        const to = packet.u as string | undefined;
        if (!to || to === username) load();
      }
    });

    return () => {
      clearInterval(pollId);
      unsub();
    };
  }, [isEngineer, username, load]);

  const value = useMemo(
    () => ({
      orders,
      latest: orders[0] ?? null,
      dismiss,
      reload: load,
    }),
    [orders, dismiss, load]
  );

  return <EngineerOrdersContext.Provider value={value}>{children}</EngineerOrdersContext.Provider>;
}

export function useEngineerOrders() {
  const ctx = useContext(EngineerOrdersContext);
  if (!ctx) {
    throw new Error('useEngineerOrders must be used within EngineerOrdersProvider');
  }
  return ctx;
}
