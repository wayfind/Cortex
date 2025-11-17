/**
 * WebSocket Hook for Real-time Updates
 *
 * Connects to Monitor WebSocket and handles real-time events
 */

import { useEffect, useRef, useCallback, useState } from 'react';
import { message as antMessage } from 'antd';

// WebSocket URL (can be configured via environment variable)
const WS_URL = import.meta.env.VITE_MONITOR_WS_URL || 'ws://localhost:18000/ws';

// Reconnect configuration
const RECONNECT_DELAY = 3000; // 3 seconds
const MAX_RECONNECT_ATTEMPTS = 10;

// WebSocket event types
export type WebSocketEventType =
  | 'report_received'
  | 'alert_triggered'
  | 'decision_made'
  | 'agent_status_changed';

export interface WebSocketEvent {
  type: WebSocketEventType;
  timestamp?: string;
  message?: string;
  [key: string]: any;
}

export interface UseWebSocketOptions {
  onMessage?: (event: WebSocketEvent) => void;
  onConnect?: () => void;
  onDisconnect?: () => void;
  onError?: (error: Event) => void;
  autoReconnect?: boolean;
  showNotifications?: boolean;
}

export function useWebSocket(options: UseWebSocketOptions = {}) {
  const {
    onMessage,
    onConnect,
    onDisconnect,
    onError,
    autoReconnect = true,
    showNotifications = true,
  } = options;

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const reconnectAttemptsRef = useRef(0);
  const [isConnected, setIsConnected] = useState(false);
  const [connectionError, setConnectionError] = useState<string | null>(null);

  const connect = useCallback(() => {
    try {
      // Cleanup existing connection
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      // Create new WebSocket connection
      const ws = new WebSocket(WS_URL);

      ws.onopen = () => {
        console.log('[WebSocket] Connected to Monitor');
        setIsConnected(true);
        setConnectionError(null);
        reconnectAttemptsRef.current = 0;

        if (showNotifications) {
          antMessage.success('Connected to real-time updates');
        }

        onConnect?.();
      };

      ws.onmessage = (event) => {
        try {
          const data: WebSocketEvent = JSON.parse(event.data);
          console.log('[WebSocket] Received:', data.type, data);

          // Show notification based on event type
          if (showNotifications) {
            switch (data.type) {
              case 'alert_triggered':
                antMessage.warning(data.message || 'New alert triggered');
                break;
              case 'decision_made':
                antMessage.info(data.message || 'Decision made');
                break;
              case 'report_received':
                // Don't show notification for reports (too frequent)
                break;
              case 'agent_status_changed':
                if (data.new_status === 'offline') {
                  antMessage.error(data.message || 'Agent went offline');
                }
                break;
            }
          }

          // Call custom message handler
          onMessage?.(data);
        } catch (err) {
          console.error('[WebSocket] Failed to parse message:', err);
        }
      };

      ws.onerror = (error) => {
        console.error('[WebSocket] Error:', error);
        setConnectionError('WebSocket connection error');
        onError?.(error);
      };

      ws.onclose = () => {
        console.log('[WebSocket] Disconnected');
        setIsConnected(false);
        wsRef.current = null;

        onDisconnect?.();

        // Auto-reconnect if enabled
        if (autoReconnect && reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS) {
          reconnectAttemptsRef.current += 1;
          console.log(
            `[WebSocket] Reconnecting... (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`
          );

          reconnectTimeoutRef.current = setTimeout(() => {
            connect();
          }, RECONNECT_DELAY);
        } else if (reconnectAttemptsRef.current >= MAX_RECONNECT_ATTEMPTS) {
          setConnectionError('Failed to reconnect after multiple attempts');
          if (showNotifications) {
            antMessage.error('Lost connection to real-time updates');
          }
        }
      };

      wsRef.current = ws;
    } catch (err) {
      console.error('[WebSocket] Failed to create connection:', err);
      setConnectionError('Failed to create WebSocket connection');
    }
  }, [onMessage, onConnect, onDisconnect, onError, autoReconnect, showNotifications]);

  const disconnect = useCallback(() => {
    if (reconnectTimeoutRef.current) {
      clearTimeout(reconnectTimeoutRef.current);
      reconnectTimeoutRef.current = null;
    }

    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    setIsConnected(false);
  }, []);

  const send = useCallback((data: any) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(data));
    } else {
      console.warn('[WebSocket] Cannot send message - not connected');
    }
  }, []);

  useEffect(() => {
    // Connect on mount
    connect();

    // Cleanup on unmount
    return () => {
      disconnect();
    };
  }, [connect, disconnect]);

  return {
    isConnected,
    connectionError,
    send,
    disconnect,
    reconnect: connect,
  };
}
