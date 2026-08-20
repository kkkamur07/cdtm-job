import {
  formatLanguageLabel,
  parseEducationTimeline,
} from "@/lib/parse-profile-timeline";

type EducationTimelineProps = {
  summary: string;
};

export function EducationTimeline({ summary }: EducationTimelineProps) {
  const entries = parseEducationTimeline(summary);

  if (entries.length === 0) return null;

  return (
    <ol className="relative space-y-7 border-l border-zinc-200 pl-6" aria-label="Education timeline">
      {entries.map((entry) => (
        <li key={entry.id} className="relative">
          <span
            className={`absolute -left-[calc(0.375rem+1px)] top-[0.45rem] h-2 w-2 rounded-full ring-4 ring-white ${
              entry.isCdtm ? "bg-cdtm" : "bg-zinc-300"
            }`}
            aria-hidden
          />
          <h3
            className={`font-display text-[1.0625rem] font-medium leading-snug tracking-tight ${
              entry.isCdtm ? "text-cdtm" : "text-zinc-900"
            }`}
          >
            {entry.title}
          </h3>
          {entry.subtitle && (
            <p className="mt-0.5 text-sm text-zinc-500">{entry.subtitle}</p>
          )}
          <p
            className={`mt-1 text-sm tabular-nums ${
              entry.isCurrent ? "text-cdtm/80" : "text-zinc-500"
            }`}
          >
            {entry.dateLabel}
          </p>
        </li>
      ))}
    </ol>
  );
}

type LanguageProfileProps = {
  languages: string[];
};

export function LanguageProfile({ languages }: LanguageProfileProps) {
  if (languages.length === 0) return null;

  return (
    <ul className="flex flex-wrap gap-2" aria-label="Languages">
      {languages.map((language) => (
        <li key={language}>
          <span className="inline-block rounded-full border border-zinc-200 bg-zinc-50 px-3 py-1 text-sm text-zinc-700">
            {formatLanguageLabel(language)}
          </span>
        </li>
      ))}
    </ul>
  );
}
