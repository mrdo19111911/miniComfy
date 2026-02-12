/**
 * WebSocket hook for real-time execution event streaming.
 */
import { useEffect, useRef, useState, useCallback } from 'react';

export interface WsEvent {
  event: string;
  [key: string]: unknown;
}

type WsHandler = (data: WsEvent) => void;

export function useWebSocket(url: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const [connected, setConnected] = useState(false);
  const handlersRef = useRef<Map<string, Set<WsHandler>>>(new Map());
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
        const handlers = handlersRef.current.get(data.event);
        if (handlers) {
          for (const h of handlers) h(data);
        }
        // Also call wildcard handlers if present
        const wildcards = handlersRef.current.get('*');
        if (wildcards) {
          for (const h of wildcards) h(data);
        }
      } catch (err) {
        console.warn('[WS] Failed to parse message:', err);
      }
    };

    wsRef.current = ws;
  }, [url]);

  const on = useCallback((event: string, handler: WsHandler) => {
    let set = handlersRef.current.get(event);
    if (!set) {
      set = new Set();
      handlersRef.current.set(event, set);
    }
    set.add(handler);
  }, []);

  const off = useCallback((event: string, handler?: WsHandler) => {
    if (handler) {
      handlersRef.current.get(event)?.delete(handler);
    } else {
      handlersRef.current.delete(event);
    }
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
