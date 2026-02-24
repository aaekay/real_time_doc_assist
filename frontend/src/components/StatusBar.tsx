import type { ConnectionStatus } from '../types';

interface StatusBarProps {
  connectionStatus: ConnectionStatus;
  isRecording: boolean;
  latencyMs: number | null;
  statusMessage?: string | null;
  errorMessage?: string | null;
  onStartRecording: () => void;
  onStopRecording: () => void;
  onEndSession: () => void;
  onReset: () => void;
}

const statusConfig: Record<ConnectionStatus, { color: string; label: string }> = {
  connecting: { color: 'bg-yellow-500', label: 'Connecting...' },
  connected: { color: 'bg-green-500', label: 'Connected' },
  disconnected: { color: 'bg-slate-500', label: 'Disconnected' },
  error: { color: 'bg-red-500', label: 'Error' },
};

export function StatusBar({
  connectionStatus,
  isRecording,
  latencyMs,
  statusMessage,
  errorMessage,
  onStartRecording,
  onStopRecording,
  onEndSession,
  onReset,
}: StatusBarProps) {
  const cfg = statusConfig[connectionStatus];

  return (
    <header className="bg-slate-900/95 border-b border-slate-700/80 px-3 md:px-4 py-2.5 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-2">
      {/* Left: Title + Status */}
      <div className="flex items-center flex-wrap gap-3">
        <h1 className="text-base md:text-lg font-bold tracking-tight text-slate-100">
          OPD Question Copilot
        </h1>
        <div className="flex items-center gap-1.5 rounded-full px-2 py-1 bg-slate-800 border border-slate-700/70">
          <div className={`w-2 h-2 rounded-full ${cfg.color} ${connectionStatus === 'connecting' ? 'animate-pulse' : ''}`} />
          <span className="text-xs text-slate-400">{cfg.label}</span>
        </div>
        {latencyMs !== null && (
          <span className="text-xs text-slate-500 bg-slate-800/70 px-2 py-1 rounded-full border border-slate-700/70">
            Pipeline: {latencyMs}ms
          </span>
        )}
        {statusMessage && (
          <span className="text-xs text-slate-500">
            {statusMessage}
          </span>
        )}
        {errorMessage && (
          <span className="text-xs text-red-400">
            {errorMessage}
          </span>
        )}
      </div>

      {/* Right: Controls */}
      <div className="flex items-center flex-wrap gap-2">
        {!isRecording ? (
          <button
            onClick={onStartRecording}
            disabled={connectionStatus !== 'connected'}
            className="px-3 py-1.5 bg-red-600 hover:bg-red-500 disabled:bg-slate-700 disabled:text-slate-500 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5"
          >
            <span className="w-2 h-2 rounded-full bg-white" />
            Start Recording
          </button>
        ) : (
          <button
            onClick={onStopRecording}
            className="px-3 py-1.5 bg-slate-600 hover:bg-slate-500 text-white text-xs font-semibold rounded-lg transition-colors flex items-center gap-1.5"
          >
            <span className="w-2 h-2 rounded-sm bg-white" />
            Stop Recording
          </button>
        )}
        <button
          onClick={onEndSession}
          className="px-3 py-1.5 bg-blue-700 hover:bg-blue-600 text-white text-xs font-semibold rounded-lg transition-colors"
        >
          End Session
        </button>
        <button
          onClick={onReset}
          className="px-3 py-1.5 bg-slate-700 hover:bg-slate-600 text-slate-300 text-xs rounded-lg transition-colors"
        >
          Reset
        </button>
      </div>
    </header>
  );
}
