"use client";

import { useEffect, useRef, useState, useCallback } from "react";

export interface ProgressEvent {
  leaflet_id: string;
  event_type: string;
  progress: number;
  message: string;
  timestamp: string;
  data: Record<string, unknown>;
}

interface UseProgressWebSocketOptions {
  /** JWT access token for authentication */
  token?: string | null;
  /** Callback when progress updates */
  onProgress?: (event: ProgressEvent) => void;
  /** Callback when extraction completes */
  onComplete?: (event: ProgressEvent) => void;
  /** Callback when error occurs */
  onError?: (event: ProgressEvent) => void;
  /** Auto-reconnect on disconnect */
  autoReconnect?: boolean;
  /** Maximum reconnection attempts */
  maxReconnectAttempts?: number;
}

interface UseProgressWebSocketReturn {
  /** Current progress (0-1) */
  progress: number;
  /** Current status message */
  message: string;
  /** Whether WebSocket is connected */
  isConnected: boolean;
  /** Whether currently reconnecting */
  isReconnecting: boolean;
  /** Last error message */
  error: string | null;
  /** Latest progress event */
  latestEvent: ProgressEvent | null;
  /** Manually disconnect */
  disconnect: () => void;
  /** Manually reconnect */
  reconnect: () => void;
}

/**
 * Compute the WebSocket base URL.
 * Prefers NEXT_PUBLIC_WS_URL, then derives from NEXT_PUBLIC_API_URL by
 * replacing the http(s) scheme with ws(s), then falls back to localhost.
 */
const WS_BASE_URL =
  process.env.NEXT_PUBLIC_WS_URL ||
  process.env.NEXT_PUBLIC_API_URL?.replace(/^http/, "ws") ||
  "ws://localhost:8000";

/** REST API base URL for the initial progress fetch (client-side). */
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

/**
 * React hook for WebSocket progress tracking.
 *
 * Connects to the backend WebSocket endpoint and receives
 * real-time progress updates for leaflet processing.
 * Fetches initial progress state via REST before connecting
 * so users see current progress immediately on page load.
 *
 * @param leafletId - The leaflet ID to track
 * @param options - Configuration options
 * @returns Progress state and controls
 *
 * @example
 * ```tsx
 * const { progress, message, isConnected } = useProgressWebSocket(leafletId, {
 *   token: authToken,
 *   onProgress: (event) => console.log('Progress:', event.progress),
 *   onComplete: (event) => console.log('Complete!'),
 * });
 * ```
 */
export function useProgressWebSocket(
  leafletId: string | null,
  options: UseProgressWebSocketOptions = {}
): UseProgressWebSocketReturn {
  const {
    token,
    onProgress,
    onComplete,
    onError,
    autoReconnect = true,
    maxReconnectAttempts = 5,
  } = options;

  const [progress, setProgress] = useState<number>(-1);
  const [message, setMessage] = useState<string>("");
  const [isConnected, setIsConnected] = useState(false);
  const [isReconnecting, setIsReconnecting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [latestEvent, setLatestEvent] = useState<ProgressEvent | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const pingIntervalRef = useRef<NodeJS.Timeout | null>(null);

  // Store callbacks in refs to avoid dependency issues
  const onProgressRef = useRef(onProgress);
  const onCompleteRef = useRef(onComplete);
  const onErrorRef = useRef(onError);

  // Store token in ref to use in createConnection without re-triggering effect
  const tokenRef = useRef(token);

  // Update refs when callbacks/token change
  useEffect(() => {
    onProgressRef.current = onProgress;
    onCompleteRef.current = onComplete;
    onErrorRef.current = onError;
    tokenRef.current = token;
  }, [onProgress, onComplete, onError, token]);

  const cleanup = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }
    if (pingIntervalRef.current) {
      clearInterval(pingIntervalRef.current);
      pingIntervalRef.current = null;
    }
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
  }, []);

  // Connect when leafletId or token changes
  useEffect(() => {
    if (!leafletId) {
      cleanup();
      return;
    }

    // Fetch initial progress via REST so the UI shows current state immediately
    const fetchInitialProgress = async () => {
      try {
        const headers: Record<string, string> = {
          "Content-Type": "application/json",
        };
        if (token) {
          headers["Authorization"] = `Bearer ${token}`;
        }
        const res = await fetch(
          `${API_BASE_URL}/api/v1/ws/progress/${leafletId}/latest`,
          { headers }
        );
        if (res.ok) {
          const data = await res.json();
          if (data.progress >= 0) {
            setProgress(data.progress);
            setMessage(data.message || "");
            setLatestEvent(data);
          }
        }
      } catch (err) {
        // Non-critical: WebSocket will deliver updates once connected
        console.warn("Failed to fetch initial progress:", err);
      }
    };

    const createConnection = () => {
      cleanup();
      setError(null);

      const currentToken = tokenRef.current;

      // Don't attempt connection without authentication token
      if (!currentToken) {
        return;
      }

      const wsUrl = currentToken
        ? `${WS_BASE_URL}/api/v1/ws/progress/${leafletId}?token=${encodeURIComponent(currentToken)}`
        : `${WS_BASE_URL}/api/v1/ws/progress/${leafletId}`;

      try {
        const ws = new WebSocket(wsUrl);
        // Ensure we receive text, not binary
        ws.binaryType = "blob";
        wsRef.current = ws;

        ws.onopen = () => {
          setIsConnected(true);
          setIsReconnecting(false);
          reconnectAttemptsRef.current = 0;
          setError(null);

          // Start ping interval
          pingIntervalRef.current = setInterval(() => {
            if (ws.readyState === WebSocket.OPEN) {
              ws.send("ping");
            }
          }, 30000);
        };

        ws.onmessage = async (event) => {
          let messageData: string;

          // Handle both Blob and string data
          if (event.data instanceof Blob) {
            messageData = await event.data.text();
          } else {
            messageData = event.data;
          }

          if (messageData === "pong") return;

          try {
            const data: ProgressEvent = JSON.parse(messageData);
            setLatestEvent(data);
            setProgress(data.progress);
            setMessage(data.message);

            // Call event-specific callbacks via refs
            if (data.event_type === "complete") {
              onCompleteRef.current?.(data);
            } else if (data.event_type === "error") {
              setError(data.message);
              onErrorRef.current?.(data);
            } else {
              onProgressRef.current?.(data);
            }
          } catch (e) {
            console.error("Failed to parse WebSocket message:", e, messageData);
          }
        };

        ws.onerror = () => {
          console.error("WebSocket error");
          setError("WebSocket connection error");
        };

        ws.onclose = (event) => {
          setIsConnected(false);
          if (pingIntervalRef.current) {
            clearInterval(pingIntervalRef.current);
            pingIntervalRef.current = null;
          }

          // Don't reconnect on auth failures (1008 = Policy Violation)
          if (event.code === 1008) {
            setError(event.reason || "Authentication failed");
            return;
          }

          // Attempt reconnection if enabled and not intentionally closed
          if (
            autoReconnect &&
            !event.wasClean &&
            reconnectAttemptsRef.current < maxReconnectAttempts
          ) {
            setIsReconnecting(true);
            reconnectAttemptsRef.current += 1;

            const delay = Math.min(
              1000 * Math.pow(2, reconnectAttemptsRef.current),
              30000
            );

            reconnectTimeoutRef.current = setTimeout(() => {
              createConnection();
            }, delay);
          }
        };
      } catch (e) {
        console.error("Failed to create WebSocket:", e);
        setError("Failed to connect");
      }
    };

    fetchInitialProgress();
    createConnection();

    return () => {
      cleanup();
    };
  }, [leafletId, autoReconnect, maxReconnectAttempts, cleanup, token]);

  const disconnect = useCallback(() => {
    reconnectAttemptsRef.current = maxReconnectAttempts; // Prevent reconnection
    cleanup();
    setIsConnected(false);
    setIsReconnecting(false);
  }, [cleanup, maxReconnectAttempts]);

  const reconnect = useCallback(() => {
    reconnectAttemptsRef.current = 0;
    // Trigger re-connection by cleaning up - the effect will reconnect
    cleanup();
    // Force a state update to trigger the effect
    setIsConnected(false);
  }, [cleanup]);

  return {
    progress,
    message,
    isConnected,
    isReconnecting,
    error,
    latestEvent,
    disconnect,
    reconnect,
  };
}

/**
 * Options for tracking multiple leaflets at once.
 */
interface UseMultiProgressWebSocketOptions {
  /** JWT access token for authentication */
  token?: string | null;
  /** Callback when progress updates */
  onProgress?: (event: ProgressEvent) => void;
  /** Callback when extraction completes */
  onComplete?: (event: ProgressEvent) => void;
  /** Callback when error occurs */
  onError?: (event: ProgressEvent) => void;
}

/**
 * Hook for tracking multiple leaflets at once.
 */
export function useMultiProgressWebSocket(
  leafletIds: string[],
  options: UseMultiProgressWebSocketOptions = {}
) {
  const { token } = options;

  const [progressMap, setProgressMap] = useState<Record<string, ProgressEvent>>({});
  const wsRef = useRef<WebSocket | null>(null);

  // Store callbacks in refs to avoid dependency issues
  const onProgressRef = useRef(options.onProgress);
  const onCompleteRef = useRef(options.onComplete);
  const onErrorRef = useRef(options.onError);

  useEffect(() => {
    onProgressRef.current = options.onProgress;
    onCompleteRef.current = options.onComplete;
    onErrorRef.current = options.onError;
  }, [options.onProgress, options.onComplete, options.onError]);

  // Memoize the IDs string to avoid unnecessary reconnects
  const idsString = leafletIds.join(",");

  useEffect(() => {
    if (leafletIds.length === 0) return;

    let wsUrl = `${WS_BASE_URL}/api/v1/ws/progress?leaflet_ids=${idsString}`;
    if (token) {
      wsUrl += `&token=${encodeURIComponent(token)}`;
    }

    const ws = new WebSocket(wsUrl);
    ws.binaryType = "blob";
    wsRef.current = ws;

    ws.onmessage = async (event: MessageEvent) => {
      let messageData: string;

      // Handle both Blob and string data
      if (event.data instanceof Blob) {
        messageData = await event.data.text();
      } else {
        messageData = event.data;
      }

      if (messageData === "pong") return;

      try {
        const data: ProgressEvent = JSON.parse(messageData);
        setProgressMap((prev) => ({
          ...prev,
          [data.leaflet_id]: data,
        }));

        if (data.event_type === "complete") {
          onCompleteRef.current?.(data);
        } else if (data.event_type === "error") {
          onErrorRef.current?.(data);
        } else {
          onProgressRef.current?.(data);
        }
      } catch (e) {
        console.error("Failed to parse message:", e, messageData);
      }
    };

    ws.onclose = (event) => {
      // Don't reconnect on auth failures (1008 = Policy Violation)
      if (event.code === 1008) {
        console.error("WebSocket auth failed:", event.reason);
      }
    };

    // Ping interval
    const pingInterval = setInterval(() => {
      if (ws.readyState === WebSocket.OPEN) {
        ws.send("ping");
      }
    }, 30000);

    return () => {
      clearInterval(pingInterval);
      ws.close();
    };
  }, [idsString, leafletIds.length, token]);

  return progressMap;
}
