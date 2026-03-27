import { useEffect, useRef, useCallback } from "react";
import { useMeetingStore } from "../stores/meetingStore";
import type { WSMessage } from "../types";

// Connect directly to backend, bypassing Vite proxy (more reliable)
const WS_URL =
  window.location.port === "5173"
    ? `ws://${window.location.hostname}:8000/ws`
    : `ws://${window.location.hostname}:${window.location.port}/ws`;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimerRef = useRef<number>(0);
  const mountedRef = useRef(true);

  const send = useCallback((msg: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify(msg));
    }
  }, []);

  useEffect(() => {
    mountedRef.current = true;

    function connect() {
      if (!mountedRef.current) return;
      if (wsRef.current?.readyState === WebSocket.OPEN) return;

      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      const store = useMeetingStore.getState;

      ws.onopen = () => {
        store().setConnected(true);
      };

      ws.onclose = () => {
        store().setConnected(false);
        wsRef.current = null;
        if (mountedRef.current) {
          reconnectTimerRef.current = window.setTimeout(connect, 2000);
        }
      };

      ws.onerror = () => {
        ws.close();
      };

      ws.onmessage = (event) => {
        const msg: WSMessage = JSON.parse(event.data);
        const s = store();

        switch (msg.type) {
          case "meeting_status":
            s.setState(msg.data.state);
            break;
          case "transcript_segment":
            s.addSegment(msg.data);
            break;
          case "suggestions_update":
            s.setSuggestions(msg.data);
            break;
          case "summary_status":
            s.setSummary("_generating_");
            break;
          case "summary":
            s.setSummary(msg.data.markdown);
            break;
          case "audio_level":
            s.setAudioLevel(msg.data.source, msg.data.level);
            break;
          case "model_download_progress":
            s.setDownloadProgress(msg.data.model, msg.data.downloaded, msg.data.total);
            break;
          case "model_downloaded":
            s.clearDownloadProgress(msg.data.model);
            fetch("/api/models")
              .then((r) => r.json())
              .then((data) => s.setModels(data.models));
            break;
          case "model_download_error":
            s.clearDownloadProgress(msg.data.model);
            break;
        }
      };
    }

    connect();

    return () => {
      mountedRef.current = false;
      clearTimeout(reconnectTimerRef.current);
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.close();
        wsRef.current = null;
      }
    };
  }, []);

  return { send };
}
