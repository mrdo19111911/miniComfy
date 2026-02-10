/**
 * WebSocket hook for real-time execution event streaming.
 */
import { useEffect, useRef, useState, useCallback } from 'react';

export interface WsEvent {
  event: string;
  [key: string]: unknown;
}

export function useWebSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef<Map<string, (data: WsEvent) => void>>(new Map());
  const reconnectTimer = useRef<ReturnType<typeof setTimeout>>();

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    const ws = new WebSocket(url);

    ws.onopen = () => {
      setConnected(true);
      console.log('[WS] Connected');
    };

    ws.onclose = () => {
      setConnected(false);
      console.log('[WS] Disconnected, reconnecting in 3s...');
      reconnectTimer.current = setTimeout(connect, 3000);
    };

    ws.onerror = () => {
      ws.close();
    };

    ws.onmessage = (msg) => {
      try {
        const data = JSON.parse(msg.data) as WsEvent;
        const handler = handlersRef.current.get(data.event);
        if (handler) handler(data);
        // Also call wildcard handler if present
        const wildcard = handlersRef.current.get('*');
        if (wildcard) wildcard(data);
      } catch (err) {
        console.warn('[WS] Failed to parse message:', err);
      }
    };

    wsRef.current = ws;
  }, [url]);

  const on = useCallback((event: string, handler: (data: WsEvent) => void) => {
    handlersRef.current.set(event, handler);
  }, []);

  const off = useCallback((event: string) => {
    handlersRef.current.delete(event);
  }, []);

  const send = useCallback((data: unknown) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    }
  }, []);

  useEffect(() => {
    connect();
    return () => {
      clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  return { connected, on, off, send };
}
