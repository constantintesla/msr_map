import { useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { commanderSocketHub, engineerSocketHub } from '../ws/hubs';
import { playMessagePing, playOrderPing } from '../utils/notificationSound';

/**
 * Incoming chat + field-order sounds for commander and engineer (not admin).
 * Mounted once in App.
 */
export function useNotificationPings() {
  const location = useLocation();

  useEffect(() => {
    const token = localStorage.getItem('token');
    const role = localStorage.getItem('role');
    if (!token || role === 'admin') return;
    if (role !== 'commander' && role !== 'engineer') return;

    const side = localStorage.getItem('side') || 'A';
    const username = localStorage.getItem('username') || '';
    const hub = role === 'commander' ? commanderSocketHub : engineerSocketHub;

    return hub.subscribe((packet) => {
      if (packet.e === 'chat') {
        const thread = (packet.thread as string | undefined) ?? 'cmd';
        const to = packet.to as string | undefined;
        if (packet.t !== side) return;
        if (packet.u && packet.u === username) return;

        if (role === 'commander') {
          if (thread !== 'cmd' && thread !== 'eng') return;
        } else {
          if (thread !== 'eng') return;
          if (to && to !== username) return;
        }
        playMessagePing();
      }
      if (packet.e === 'field_order' && role === 'engineer' && packet.u === username) {
        playOrderPing();
      }
      if (
        packet.e === 'field_order_update' &&
        role === 'engineer' &&
        packet.u === username &&
        !packet.ack
      ) {
        playOrderPing();
      }
    });
  }, [location.pathname]);
}

function NotificationPings() {
  useNotificationPings();
  return null;
}

export default NotificationPings;
