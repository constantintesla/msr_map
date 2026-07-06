export type SocketPacket = Record<string, unknown>;
type MessageHandler = (packet: SocketPacket) => void;

/** Survives React StrictMode mount → unmount → remount without tearing CONNECTING sockets. */
const DISCONNECT_GRACE_MS = 100;

function safeClose(ws: WebSocket | null) {
  if (!ws) return;
  ws.onmessage = null;
  ws.onerror = null;
  ws.onclose = null;
  if (ws.readyState === WebSocket.CONNECTING) {
    const pending = ws;
    pending.onopen = () => pending.close();
  } else if (ws.readyState === WebSocket.OPEN) {
    ws.close();
  }
}

export function createSocketHub(getUrl: () => string) {
  let ws: WebSocket | null = null;
  let subscribers = 0;
  const handlers = new Set<MessageHandler>();
  let reconnectTimer: ReturnType<typeof setTimeout> | undefined;
  let disconnectTimer: ReturnType<typeof setTimeout> | undefined;

  function connect() {
    if (subscribers === 0) return;
    if (ws?.readyState === WebSocket.OPEN || ws?.readyState === WebSocket.CONNECTING) return;

    const socket = new WebSocket(getUrl());
    ws = socket;

    socket.onmessage = (ev) => {
      try {
        const packet = JSON.parse(ev.data) as SocketPacket;
        handlers.forEach((handler) => handler(packet));
      } catch {
        // ignore malformed packets
      }
    };
    socket.onclose = (ev) => {
      if (ws !== socket) return;
      ws = null;
      if (ev.code === 4401 || subscribers === 0) return;
      clearTimeout(reconnectTimer);
      reconnectTimer = setTimeout(connect, 3000);
    };
    socket.onerror = () => {
      // onclose handles reconnect
    };
  }

  function subscribe(handler: MessageHandler) {
    clearTimeout(disconnectTimer);
    subscribers += 1;
    handlers.add(handler);
    connect();

    return () => {
      handlers.delete(handler);
      subscribers -= 1;
      if (subscribers > 0) return;

      disconnectTimer = setTimeout(() => {
        if (subscribers > 0) return;
        clearTimeout(reconnectTimer);
        safeClose(ws);
        ws = null;
      }, DISCONNECT_GRACE_MS);
    };
  }

  return { subscribe };
}
