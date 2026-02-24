import type { SOAPNote } from '../types';

interface SummaryPanelProps {
  soapNote: SOAPNote | null;
  onClose: () => void;
}

export function SummaryPanel({ soapNote, onClose }: SummaryPanelProps) {
  if (!soapNote) return null;

  const sections = [
    { label: 'Subjective', content: soapNote.subjective, color: 'border-blue-500' },
    { label: 'Objective', content: soapNote.objective, color: 'border-green-500' },
    { label: 'Assessment', content: soapNote.assessment, color: 'border-orange-500' },
    { label: 'Plan', content: soapNote.plan, color: 'border-purple-500' },
  ];

  return (
    <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50 p-4">
      <div className="bg-slate-800 rounded-xl border border-slate-600 max-w-2xl w-full max-h-[85vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-700 flex items-center justify-between">
          <h2 className="text-lg font-semibold text-slate-100">SOAP Note</h2>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 transition-colors text-xl leading-none"
          >
            &times;
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-4">
          {sections.map((s) => (
            <div key={s.label} className={`border-l-2 ${s.color} pl-4`}>
              <h3 className="text-xs font-bold text-slate-400 uppercase tracking-wider mb-1">
                {s.label}
              </h3>
              <p className="text-sm text-slate-200 whitespace-pre-wrap leading-relaxed">
                {s.content}
              </p>
            </div>
          ))}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-700 flex justify-end">
          <button
            onClick={() => {
              const text = sections.map((s) => `${s.label}:\n${s.content}`).join('\n\n');
              navigator.clipboard.writeText(text);
            }}
            className="text-xs text-slate-400 hover:text-slate-200 transition-colors mr-4"
          >
            Copy to clipboard
          </button>
          <button
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-700 hover:bg-slate-600 text-sm text-slate-200 rounded transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
