import { useEffect, useRef } from 'react';

interface TranscriptPanelProps {
  transcript: string;
}

type TranscriptSpeaker = 'Doctor' | 'Patient' | 'Unknown';

function parseTranscriptLine(line: string): { speaker: TranscriptSpeaker; content: string } {
  const trimmed = line.trim();
  const lower = trimmed.toLowerCase();
  if (lower.startsWith('doctor:')) {
    return { speaker: 'Doctor', content: trimmed.slice(7).trim() };
  }
  if (lower.startsWith('patient:')) {
    return { speaker: 'Patient', content: trimmed.slice(8).trim() };
  }
  return { speaker: 'Unknown', content: trimmed };
}

export function TranscriptPanel({ transcript }: TranscriptPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [transcript]);

  const parsedLines = transcript
    .split('\n')
    .filter(Boolean)
    .map(parseTranscriptLine);

  return (
    <div className="flex flex-col h-full bg-slate-800/90 rounded-xl border border-slate-700/80 shadow-[0_8px_24px_-18px_rgba(0,0,0,0.8)]">
      <div className="px-4 py-3 border-b border-slate-700/80 flex items-center justify-between">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Live Transcript
        </h2>
        {parsedLines.length > 0 && (
          <span className="text-[11px] text-slate-500">{parsedLines.length} lines</span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-2.5">
        {parsedLines.length === 0 ? (
          <p className="text-slate-500 text-sm italic">
            Waiting for conversation...
          </p>
        ) : (
          parsedLines.map((entry, i) => {
            const speakerStyles =
              entry.speaker === 'Doctor'
                ? 'border-blue-500/30 bg-blue-950/20'
                : entry.speaker === 'Patient'
                  ? 'border-emerald-500/30 bg-emerald-950/20'
                  : 'border-slate-600/40 bg-slate-700/30';

            const tagStyles =
              entry.speaker === 'Doctor'
                ? 'text-blue-200 bg-blue-500/20'
                : entry.speaker === 'Patient'
                  ? 'text-emerald-200 bg-emerald-500/20'
                  : 'text-slate-300 bg-slate-600/40';

            return (
              <div
                key={`${entry.speaker}-${i}`}
                className={`rounded-lg border p-3 ${speakerStyles}`}
              >
                <div className="mb-1.5">
                  <span className={`text-[10px] uppercase tracking-wide px-1.5 py-0.5 rounded ${tagStyles}`}>
                    {entry.speaker}
                  </span>
                </div>
                <p className="text-sm text-slate-100 leading-relaxed">{entry.content || '...'}</p>
              </div>
            );
          })
        )}
        <div ref={bottomRef} />
      </div>
    </div>
  );
}
