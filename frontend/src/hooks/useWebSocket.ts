import { useCallback, useEffect, useRef, useState } from 'react';
import type {
  WSMessage,
  ConnectionStatus,
  KeywordSuggestionGroup,
  EncounterStateData,
  SOAPNote,
  SessionResetPayload,
} from '../types';

interface UseWebSocketReturn {
  status: ConnectionStatus;
  transcript: string;
  keywordSuggestions: KeywordSuggestionGroup[];
  encounterState: EncounterStateData | null;
  soapNote: SOAPNote | null;
  latencyMs: number | null;
  statusMessage: string | null;
  error: string | null;
  sendAudio: (data: ArrayBuffer) => void;
  sendControl: (action: string, payload?: Record<string, unknown>) => void;
}

const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/ws`;

export function useWebSocket(): UseWebSocketReturn {
  const wsRef = useRef<WebSocket | null>(null);
  const [status, setStatus] = useState<ConnectionStatus>('connecting');
  const [transcript, setTranscript] = useState('');
  const [keywordSuggestions, setKeywordSuggestions] = useState<KeywordSuggestionGroup[]>([]);
  const [encounterState, setEncounterState] = useState<EncounterStateData | null>(null);
  const [soapNote, setSoapNote] = useState<SOAPNote | null>(null);
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const clearSessionState = useCallback(() => {
    setTranscript('');
    setKeywordSuggestions([]);
    setEncounterState(null);
    setSoapNote(null);
    setLatencyMs(null);
    setError(null);
  }, []);

  useEffect(() => {
    const ws = new WebSocket(WS_URL);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      setError(null);
      setStatusMessage(null);
    };

    ws.onclose = () => {
      setStatus('disconnected');
    };

    ws.onerror = () => {
      setStatus('error');
      setError('WebSocket connection failed');
    };

    ws.onmessage = (event) => {
      try {
        const msg: WSMessage = JSON.parse(event.data);
        switch (msg.type) {
          case 'transcript':
            setTranscript((msg.data as { full: string }).full);
            break;
          case 'keyword_suggestions':
            setKeywordSuggestions(
              (msg.data as { groups: KeywordSuggestionGroup[] }).groups ?? [],
            );
            break;
          case 'encounter_state':
            setEncounterState(msg.data as unknown as EncounterStateData);
            break;
          case 'soap_note':
            setSoapNote(msg.data as unknown as SOAPNote);
            break;
          case 'session_reset': {
            const d = msg.data as unknown as SessionResetPayload;
            setTranscript(d.transcript);
            setKeywordSuggestions(d.keyword_suggestions ?? []);
            setEncounterState(d.encounter_state);
            setSoapNote(d.soap_note);
            setLatencyMs(d.pipeline_latency_ms);
            setStatusMessage(d.message);
            setError(null);
            break;
          }
          case 'status': {
            const d = msg.data as Record<string, unknown>;
            if (typeof d.pipeline_latency_ms === 'number') {
              setLatencyMs(d.pipeline_latency_ms as number);
            }
            if (typeof d.message === 'string') {
              setStatusMessage(d.message);
            }
            break;
          }
          case 'error':
            setError((msg.data as { message: string }).message);
            break;
        }
      } catch (err) {
        console.warn('[useWebSocket] Failed to parse message:', err);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  const sendAudio = useCallback((data: ArrayBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(data);
    }
  }, []);

  const sendControl = useCallback((action: string, payload?: Record<string, unknown>) => {
    if (action === 'reset') {
      clearSessionState();
      setStatusMessage('Reset requested...');
    }
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ action, ...payload }));
    }
  }, [clearSessionState]);

  return {
    status,
    transcript,
    keywordSuggestions,
    encounterState,
    soapNote,
    latencyMs,
    statusMessage,
    error,
    sendAudio,
    sendControl,
  };
}
