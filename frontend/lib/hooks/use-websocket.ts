"use client";

import { useEffect, useRef, useState, useCallback } from 'react';
import { toast } from 'sonner';

export interface WebSocketMessage {
  type: string;
  data: unknown;
  timestamp: string;
}

export interface WebSocketHookOptions {
  url: string;
  protocols?: string | string[];
  onMessage?: (message: WebSocketMessage) => void;
  onError?: (error: Event) => void;
  onOpen?: (event: Event) => void;
  onClose?: (event: CloseEvent) => void;
  shouldReconnect?: boolean;
  reconnectInterval?: number;
  maxReconnectAttempts?: number;
  heartbeatInterval?: number;
}

export interface WebSocketHookReturn {
  socket: WebSocket | null;
  connectionStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  sendMessage: (message: Record<string, unknown>) => void;
  disconnect: () => void;
  reconnect: () => void;
  lastMessage: WebSocketMessage | null;
  reconnectAttempts: number;
}

/**
 * Robust WebSocket hook.
 *
 * Why the refs:
 *   - The heartbeat interval and the onclose reconnect timer both run
 *     long after they're scheduled. If we read `socket` or
 *     `reconnectAttempts` from React state inside those callbacks, we
 *     capture the *first* render's values and never see updates.
 *   - We store the live socket, current reconnect-attempt count, and
 *     latest user callbacks in refs so the long-lived timers always
 *     operate on current data.
 */
export function useWebSocket({
  url,
  protocols,
  onMessage,
  onError,
  onOpen,
  onClose,
  shouldReconnect = true,
  reconnectInterval = 3000,
  maxReconnectAttempts = 5,
  heartbeatInterval = 30000,
}: WebSocketHookOptions): WebSocketHookReturn {
  const [socket, setSocket] = useState<WebSocket | null>(null);
  const [connectionStatus, setConnectionStatus] = useState<'connecting' | 'connected' | 'disconnected' | 'error'>('disconnected');
  const [lastMessage, setLastMessage] = useState<WebSocketMessage | null>(null);
  const [reconnectAttempts, setReconnectAttempts] = useState(0);

  // Refs for everything that long-lived timers need to read.
  const socketRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const heartbeatIntervalRef = useRef<ReturnType<typeof setInterval> | undefined>(undefined);
  const shouldReconnectRef = useRef(shouldReconnect);
  const urlRef = useRef(url);
  const protocolsRef = useRef(protocols);

  // Mirror user callbacks into refs so we can call the latest version
  // from inside event handlers without re-creating `connect()` on every
  // parent render.
  const onMessageRef = useRef(onMessage);
  const onErrorRef = useRef(onError);
  const onOpenRef = useRef(onOpen);
  const onCloseRef = useRef(onClose);

  // Ref for connect function so the onclose handler can call it without
  // a circular dependency between useCallback hooks.
  const connectRef = useRef<() => void>(() => {});

  useEffect(() => {
    shouldReconnectRef.current = shouldReconnect;
    urlRef.current = url;
    protocolsRef.current = protocols;
    onMessageRef.current = onMessage;
    onErrorRef.current = onError;
    onOpenRef.current = onOpen;
    onCloseRef.current = onClose;
  }, [shouldReconnect, url, protocols, onMessage, onError, onOpen, onClose]);

  const clearTimeouts = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = undefined;
    }
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = undefined;
    }
  }, []);

  const startHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
    }
    if (heartbeatInterval > 0) {
      heartbeatIntervalRef.current = setInterval(() => {
        const liveSocket = socketRef.current;
        if (liveSocket?.readyState === WebSocket.OPEN) {
          liveSocket.send(
            JSON.stringify({ type: 'ping', timestamp: new Date().toISOString() })
          );
        }
      }, heartbeatInterval);
    }
  }, [heartbeatInterval]);

  const stopHeartbeat = useCallback(() => {
    if (heartbeatIntervalRef.current) {
      clearInterval(heartbeatIntervalRef.current);
      heartbeatIntervalRef.current = undefined;
    }
  }, []);

  const connect = useCallback(() => {
    try {
      setConnectionStatus('connecting');
      const ws = protocolsRef.current
        ? new WebSocket(urlRef.current, protocolsRef.current)
        : new WebSocket(urlRef.current);

      socketRef.current = ws;
      setSocket(ws);

      ws.onopen = (event) => {
        setConnectionStatus('connected');
        reconnectAttemptsRef.current = 0;
        setReconnectAttempts(0);
        startHeartbeat();
        onOpenRef.current?.(event);
      };

      ws.onmessage = (event) => {
        try {
          const message: WebSocketMessage = JSON.parse(event.data);

          // Handle ping/pong
          if (message.type === 'ping') {
            ws.send(JSON.stringify({ type: 'pong', timestamp: new Date().toISOString() }));
            return;
          }

          if (message.type === 'pong') {
            return;
          }

          setLastMessage(message);
          onMessageRef.current?.(message);
        } catch (error) {
          console.warn('Failed to parse WebSocket message:', error);
        }
      };

      ws.onclose = (event) => {
        setConnectionStatus('disconnected');
        stopHeartbeat();
        if (reconnectTimeoutRef.current) {
          clearTimeout(reconnectTimeoutRef.current);
          reconnectTimeoutRef.current = undefined;
        }

        onCloseRef.current?.(event);

        // Attempt to reconnect if enabled and not a clean close.
        // Read the live attempt count from the ref — using React state
        // here would compare against a stale snapshot and either spin
        // forever or stop too early.
        if (
          shouldReconnectRef.current &&
          event.code !== 1000 &&
          reconnectAttemptsRef.current < maxReconnectAttempts
        ) {
          reconnectAttemptsRef.current += 1;
          setReconnectAttempts(reconnectAttemptsRef.current);
          reconnectTimeoutRef.current = setTimeout(() => {
            connectRef.current();
          }, reconnectInterval);
        } else if (reconnectAttemptsRef.current >= maxReconnectAttempts) {
          setConnectionStatus('error');
          toast.error('Connection lost. Please refresh the page to reconnect.');
        }
      };

      ws.onerror = (error) => {
        setConnectionStatus('error');
        onErrorRef.current?.(error);
        console.error('WebSocket error:', error);
      };
    } catch (error) {
      setConnectionStatus('error');
      console.error('Failed to create WebSocket connection:', error);
    }
  }, [startHeartbeat, stopHeartbeat, reconnectInterval, maxReconnectAttempts]);

  // Keep the ref in sync with the latest connect callback
  useEffect(() => {
    connectRef.current = connect;
  }, [connect]);

  const disconnect = useCallback(() => {
    shouldReconnectRef.current = false;
    clearTimeouts();
    stopHeartbeat();

    const liveSocket = socketRef.current;
    if (
      liveSocket?.readyState === WebSocket.OPEN ||
      liveSocket?.readyState === WebSocket.CONNECTING
    ) {
      liveSocket.close(1000, 'Manual disconnect');
    }

    socketRef.current = null;
    setSocket(null);
    setConnectionStatus('disconnected');
  }, [clearTimeouts, stopHeartbeat]);

  const reconnect = useCallback(() => {
    disconnect();
    reconnectAttemptsRef.current = 0;
    setReconnectAttempts(0);
    shouldReconnectRef.current = true;
    setTimeout(connect, 100); // Small delay to ensure cleanup
  }, [disconnect, connect]);

  const sendMessage = useCallback(
    (message: Record<string, unknown>) => {
      const liveSocket = socketRef.current;
      if (liveSocket?.readyState === WebSocket.OPEN) {
        const messageWithTimestamp = {
          ...message,
          timestamp: new Date().toISOString(),
        };
        liveSocket.send(JSON.stringify(messageWithTimestamp));
      } else {
        console.warn('WebSocket is not open. Message not sent:', message);
        toast.warning('Connection lost. Trying to reconnect...');
        if (shouldReconnectRef.current) {
          reconnect();
        }
      }
    },
    [reconnect]
  );

  // Initial connection + cleanup on unmount.
  // We defer `connect()` to the next microtick so that the setState
  // calls inside it are not considered synchronous within the effect
  // body, satisfying the react-hooks/set-state-in-effect rule.
  useEffect(() => {
    const handle = setTimeout(() => {
      connectRef.current();
    }, 0);

    return () => {
      clearTimeout(handle);
      shouldReconnectRef.current = false;
      clearTimeouts();
      stopHeartbeat();
      const liveSocket = socketRef.current;
      if (liveSocket) {
        liveSocket.close(1000, 'Component unmounting');
      }
      socketRef.current = null;
    };
  }, [clearTimeouts, stopHeartbeat]);

  return {
    socket,
    connectionStatus,
    sendMessage,
    disconnect,
    reconnect,
    lastMessage,
    reconnectAttempts,
  };
}
