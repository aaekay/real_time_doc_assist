import type { ChiefComplaintStructured } from '../types';

interface ChiefComplaintPanelProps {
  chiefComplaint: string | null;
  structured: ChiefComplaintStructured | null;
}

function buildChiefComplaintLine(
  chiefComplaint: string | null,
  structured: ChiefComplaintStructured | null,
): string | null {
  if (structured) {
    const primary = structured.primary?.trim() || chiefComplaint?.trim() || '';
    const segments: string[] = [];
    if (primary) {
      segments.push(primary);
    }
    if (structured.site?.trim()) {
      segments.push(`in ${structured.site.trim()}`);
    }
    if (structured.duration?.trim()) {
      segments.push(`x ${structured.duration.trim()}`);
    }
    if (structured.onset?.trim()) {
      segments.push(`(${structured.onset.trim()})`);
    }
    if (structured.character?.trim()) {
      segments.push(`— ${structured.character.trim()}`);
    }
    if (structured.severity?.trim()) {
      segments.push(`[${structured.severity.trim()}]`);
    }
    if (structured.radiation?.trim()) {
      segments.push(`→ ${structured.radiation.trim()}`);
    }
    if (structured.time_course?.trim()) {
      segments.push(`; ${structured.time_course.trim()}`);
    }
    if (structured.characteristics.length > 0) {
      segments.push(`; ${structured.characteristics.join(', ')}`);
    }
    if (structured.associated.length > 0) {
      segments.push(`with ${structured.associated.join(', ')}`);
    }
    if (segments.length > 0) {
      return segments.join(' ');
    }
  }

  if (chiefComplaint?.trim()) {
    return chiefComplaint.trim();
  }

  return null;
}

/** Render a label + value pair inline. */
function DetailItem({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-[11px] text-slate-400 uppercase tracking-wide">{label}</span>
      <span className="text-xs px-2 py-1 rounded-full bg-slate-700 text-slate-100">
        {value}
      </span>
    </div>
  );
}

/** Render a chip array section. */
function ChipSection({
  label,
  items,
  borderColor,
  bgColor,
  textColor,
}: {
  label: string;
  items: string[];
  borderColor: string;
  bgColor: string;
  textColor: string;
}) {
  if (items.length === 0) return null;
  return (
    <div>
      <p className="text-[11px] text-slate-400 uppercase tracking-wide mb-1">{label}</p>
      <div className="flex flex-wrap gap-1.5">
        {items.map((item) => (
          <span
            key={`${label}-${item}`}
            className={`text-[11px] px-2 py-1 rounded-full border ${borderColor} ${bgColor} ${textColor}`}
          >
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

export function ChiefComplaintPanel({
  chiefComplaint,
  structured,
}: ChiefComplaintPanelProps) {
  const line = buildChiefComplaintLine(chiefComplaint, structured);

  // Scalar SOCRATES fields
  const duration = structured?.duration?.trim() ?? '';
  const onset = structured?.onset?.trim() ?? '';
  const site = structured?.site?.trim() ?? '';
  const character = structured?.character?.trim() ?? '';
  const radiation = structured?.radiation?.trim() ?? '';
  const severity = structured?.severity?.trim() ?? '';
  const timeCourse = structured?.time_course?.trim() ?? '';

  // List fields
  const characteristics = structured?.characteristics ?? [];
  const associated = structured?.associated ?? [];
  const aggravating = structured?.aggravating ?? [];
  const relieving = structured?.relieving ?? [];

  const hasDetails =
    duration || onset || site || character || radiation || severity || timeCourse ||
    characteristics.length > 0 || associated.length > 0 ||
    aggravating.length > 0 || relieving.length > 0;

  return (
    <div className="flex flex-col h-full bg-slate-800/90 rounded-xl border border-slate-700/80 shadow-[0_8px_24px_-18px_rgba(0,0,0,0.8)]">
      <div className="px-4 py-3 border-b border-slate-700/80">
        <h2 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Chief Complaint
        </h2>
      </div>
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {!line ? (
          <p className="text-slate-500 text-sm italic">
            Waiting for complaint details from conversation...
          </p>
        ) : (
          <div className="rounded-lg border border-cyan-500/30 bg-cyan-950/20 p-3">
            <p className="text-[11px] uppercase tracking-wide text-cyan-300/80 mb-1">
              Structured Summary
            </p>
            <p className="text-sm text-slate-100 leading-relaxed">{line}</p>
          </div>
        )}

        {hasDetails && (
          <div className="space-y-2">
            {onset && <DetailItem label="Onset" value={onset} />}
            {site && <DetailItem label="Site" value={site} />}
            {duration && <DetailItem label="Duration" value={duration} />}
            {character && <DetailItem label="Character" value={character} />}
            {radiation && <DetailItem label="Radiation" value={radiation} />}
            {severity && <DetailItem label="Severity" value={severity} />}
            {timeCourse && <DetailItem label="Time Course" value={timeCourse} />}

            <ChipSection
              label="Characteristics"
              items={characteristics}
              borderColor="border-blue-400/30"
              bgColor="bg-blue-500/10"
              textColor="text-blue-100"
            />

            <ChipSection
              label="Associated Symptoms"
              items={associated}
              borderColor="border-emerald-400/30"
              bgColor="bg-emerald-500/10"
              textColor="text-emerald-100"
            />

            <ChipSection
              label="Aggravating Factors"
              items={aggravating}
              borderColor="border-red-400/30"
              bgColor="bg-red-500/10"
              textColor="text-red-100"
            />

            <ChipSection
              label="Relieving Factors"
              items={relieving}
              borderColor="border-green-400/30"
              bgColor="bg-green-500/10"
              textColor="text-green-100"
            />
          </div>
        )}
      </div>
    </div>
  );
}
