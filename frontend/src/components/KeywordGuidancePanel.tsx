import type { KeywordSuggestionGroup, QuestionPriority } from '../types';

interface KeywordGuidancePanelProps {
  groups: KeywordSuggestionGroup[];
}

const priorityStyles: Record<QuestionPriority, string> = {
  critical: 'border-red-500/50 bg-red-950/30 text-red-200',
  high: 'border-orange-500/40 bg-orange-950/25 text-orange-200',
  medium: 'border-blue-500/35 bg-blue-950/20 text-blue-200',
  low: 'border-slate-600/35 bg-slate-700/30 text-slate-200',
};

const chipStyles: Record<QuestionPriority, string> = {
  critical: 'bg-red-500/15 text-red-100 border-red-400/40',
  high: 'bg-orange-500/15 text-orange-100 border-orange-400/40',
  medium: 'bg-blue-500/15 text-blue-100 border-blue-400/40',
  low: 'bg-slate-500/20 text-slate-100 border-slate-400/30',
};

export function KeywordGuidancePanel({ groups }: KeywordGuidancePanelProps) {
  const totalKeywords = groups.reduce((sum, group) => sum + group.keywords.length, 0);

  return (
    <div className="flex flex-col h-full bg-slate-800/90 rounded-xl border border-slate-700/80 shadow-[0_8px_24px_-18px_rgba(0,0,0,0.8)]">
      <div className="px-4 py-3 border-b border-slate-700/80 flex items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Suggested Focus Keywords
        </h2>
        {groups.length > 0 && (
          <span className="text-[11px] text-slate-500">
            {groups.length} groups • {totalKeywords} keywords
          </span>
        )}
      </div>
      <div className="flex-1 overflow-y-auto p-3 space-y-2.5">
        {groups.length === 0 ? (
          <p className="text-slate-500 text-sm italic p-1">
            Keyword guidance will appear as the conversation progresses...
          </p>
        ) : (
          groups.map((group, idx) => (
            <section
              key={`${group.category}-${group.priority}`}
              className={`rounded-lg border p-3 panel-pop ${priorityStyles[group.priority]}`}
              style={{ animationDelay: `${Math.min(idx * 70, 280)}ms` }}
            >
              <div className="flex items-center justify-between mb-2 gap-2">
                <h3 className="text-sm font-semibold">{group.category}</h3>
                <span className="text-[10px] uppercase tracking-wide opacity-80">
                  {group.priority}
                </span>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {group.keywords.map((keyword) => (
                  <span
                    key={`${group.category}-${keyword}`}
                    className={`text-[11px] px-2 py-1 rounded-full border ${chipStyles[group.priority]}`}
                  >
                    {keyword}
                  </span>
                ))}
              </div>

              {group.rationale && (
                <p className="text-xs mt-2 opacity-80">{group.rationale}</p>
              )}
            </section>
          ))
        )}
      </div>
    </div>
  );
}
