import type { DemographicsData } from '../types';

interface DemographicsPanelProps {
  demographics: DemographicsData | null;
}

function valueOrPending(value: string | null | undefined) {
  if (!value) {
    return <span className="text-slate-500 italic">Not captured yet</span>;
  }
  return <span className="text-slate-100">{value}</span>;
}

function completionCount(demographics: DemographicsData | null): number {
  let count = 0;
  if (demographics?.name) count += 1;
  if (demographics?.age) count += 1;
  if (demographics?.sex) count += 1;
  return count;
}

export function DemographicsPanel({ demographics }: DemographicsPanelProps) {
  const completed = completionCount(demographics);

  return (
    <div className="h-full bg-slate-800/90 rounded-xl border border-slate-700/80 shadow-[0_8px_24px_-18px_rgba(0,0,0,0.8)] px-3 md:px-4 py-2.5 flex flex-col gap-2">
      <div className="flex items-center justify-between">
        <h2 className="text-[11px] font-semibold text-slate-300 uppercase tracking-[0.16em]">
          Demographics
        </h2>
        <span className="text-[11px] text-slate-500">{completed}/3 captured</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-2 text-xs min-h-0">
        <div className="rounded-lg border border-slate-700/70 bg-slate-900/40 px-2.5 py-2 flex items-center justify-between gap-2">
          <span className="text-slate-400 uppercase tracking-wide">Name</span>
          {valueOrPending(demographics?.name)}
        </div>
        <div className="rounded-lg border border-slate-700/70 bg-slate-900/40 px-2.5 py-2 flex items-center justify-between gap-2">
          <span className="text-slate-400 uppercase tracking-wide">Age</span>
          {valueOrPending(demographics?.age)}
        </div>
        <div className="rounded-lg border border-slate-700/70 bg-slate-900/40 px-2.5 py-2 flex items-center justify-between gap-2">
          <span className="text-slate-400 uppercase tracking-wide">Sex</span>
          {valueOrPending(demographics?.sex)}
        </div>

        <div className="rounded-lg border border-slate-700/70 bg-slate-900/40 px-2.5 py-2">
          <p className="text-slate-400 uppercase tracking-wide mb-1">Other</p>
          {!demographics?.other || demographics.other.length === 0 ? (
            <p className="text-slate-500 italic">None</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {demographics.other.map((item) => (
                <span
                  key={item}
                  className="text-[11px] px-2 py-0.5 rounded-full bg-slate-700 text-slate-200"
                >
                  {item}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
