type EducationTimelineEntry = {
  id: string;
  title: string;
  subtitle?: string;
  startYear: number;
  endYear: number | null;
  isCurrent: boolean;
  dateLabel: string;
  isCdtm: boolean;
};

function cleanSegment(segment: string): string {
  return segment.replace(/\s+/g, " ").trim();
}

function formatDateLabel(startYear: number, endYear: number | null, isCurrent: boolean): string {
  if (isCurrent || endYear == null) {
    return `${startYear} to Present`;
  }
  if (startYear === endYear) {
    return `${startYear}`;
  }
  return `${startYear} to ${endYear}`;
}

function parseLeadingDateRange(
  segment: string,
): { startYear: number; endYear: number | null; isCurrent: boolean; rest: string } | null {
  const match = segment.match(
    /^(\d{4})\s*[–\-—]\s*(Present|present|ongoing|\d{4})\s*·\s*(.+)$/i,
  );
  if (!match) return null;

  const startYear = Number.parseInt(match[1], 10);
  const endToken = match[2];
  const isCurrent = /present|ongoing/i.test(endToken);
  const endYear = isCurrent ? null : Number.parseInt(endToken, 10);
  return { startYear, endYear, isCurrent, rest: cleanSegment(match[3]) };
}

function inferDatesFromHints(
  segment: string,
): { startYear: number; endYear: number | null; isCurrent: boolean } {
  const classOf = segment.match(/\bclass of (\d{4})\b/i);
  if (classOf) {
    const year = Number.parseInt(classOf[1], 10);
    return { startYear: year - 1, endYear: year, isCurrent: false };
  }

  const elective = segment.match(/\bcdtm elective(?: (\d{4}))?\b/i);
  if (elective) {
    const year = elective[1] ? Number.parseInt(elective[1], 10) : new Date().getFullYear();
    return { startYear: year - 1, endYear: year, isCurrent: false };
  }

  if (/\bvisiting term\b/i.test(segment)) {
    const year = new Date().getFullYear() - 1;
    return { startYear: year, endYear: year, isCurrent: false };
  }

  if (/\(ongoing\)/i.test(segment)) {
    const isMasters = /\bm\.(sc|a)\./i.test(segment);
    const isBachelors = /\bb\.(sc|a)\./i.test(segment);
    const span = isMasters ? 2 : isBachelors ? 3 : 2;
    const endYear = new Date().getFullYear();
    return { startYear: endYear - span, endYear: null, isCurrent: true };
  }

  const years = [...segment.matchAll(/\b(20\d{2})\b/g)].map((m) => Number.parseInt(m[1], 10));
  if (years.length >= 2) {
    return { startYear: years[0], endYear: years[years.length - 1], isCurrent: false };
  }
  if (years.length === 1) {
    return { startYear: years[0], endYear: years[0], isCurrent: false };
  }

  if (/^cdtm$/i.test(segment.trim())) {
    const year = new Date().getFullYear();
    return { startYear: year - 1, endYear: year, isCurrent: false };
  }

  const isMasters = /\bm\.(sc|a)\./i.test(segment);
  const fallbackEnd = new Date().getFullYear();
  return {
    startYear: fallbackEnd - (isMasters ? 2 : 4),
    endYear: fallbackEnd,
    isCurrent: false,
  };
}

function stripHints(text: string): string {
  return cleanSegment(
    text
      .replace(/\(ongoing\)/gi, "")
      .replace(/\bclass of \d{4}\b/gi, "")
      .replace(/\bcdtm elective(?: \d{4})?\b/gi, "")
      .replace(/\bvisiting term\b/gi, "")
      .replace(/\s*,\s*$/, ""),
  );
}

function splitOrganizationDetail(text: string): { organization: string; detail?: string } {
  const cleaned = stripHints(text);
  const comma = cleaned.indexOf(",");
  if (comma === -1) {
    return { organization: cleaned };
  }
  return {
    organization: cleaned.slice(0, comma).trim(),
    detail: cleaned.slice(comma + 1).trim() || undefined,
  };
}

function buildTitle(organization: string, detail?: string): string {
  if (detail) {
    return `${organization}, ${detail}`;
  }
  return organization;
}

function buildSubtitle(isCdtm: boolean): string | undefined {
  if (!isCdtm) return undefined;
  return "CDTM · Munich, Germany";
}

function splitSummarySegments(summary: string): string[] {
  const lines = summary.split(/\n+/).map(cleanSegment).filter(Boolean);
  const segments: string[] = [];

  for (const line of lines) {
    if (/^\d{4}\s*[–\-—]/.test(line)) {
      segments.push(...line.split(/\s*·\s*(?=\d{4}\s*[–\-—])/));
      continue;
    }

    if (line.includes(" · ")) {
      segments.push(...line.split(/\s*·\s+/));
      continue;
    }

    segments.push(line);
  }

  return segments.map(cleanSegment).filter(Boolean);
}

function sortKey(entry: EducationTimelineEntry): number {
  const end = entry.isCurrent ? 9999 : (entry.endYear ?? entry.startYear);
  return end * 100 + entry.startYear;
}

export function parseEducationTimeline(summary: string): EducationTimelineEntry[] {
  const segments = splitSummarySegments(summary);

  const entries = segments.map((segment, index) => {
    const isCdtm = /cdtm/i.test(segment);
    const leading = parseLeadingDateRange(segment);

    let startYear: number;
    let endYear: number | null;
    let isCurrent: boolean;
    let body: string;

    if (leading) {
      ({ startYear, endYear, isCurrent, rest: body } = leading);
    } else {
      body = segment;
      ({ startYear, endYear, isCurrent } = inferDatesFromHints(segment));
    }

    const { organization, detail } = splitOrganizationDetail(body);
    const entryIsCdtm = isCdtm || /^cdtm$/i.test(organization);

    return {
      id: `${index}-${organization.slice(0, 24)}`,
      title: buildTitle(organization, detail),
      subtitle: buildSubtitle(entryIsCdtm),
      startYear,
      endYear,
      isCurrent,
      dateLabel: formatDateLabel(startYear, endYear, isCurrent),
      isCdtm: entryIsCdtm,
    };
  });

  return entries.sort((a, b) => sortKey(b) - sortKey(a));
}

export function formatLanguageLabel(language: string): string {
  const trimmed = language.trim();
  if (!trimmed) return trimmed;
  return trimmed.charAt(0).toUpperCase() + trimmed.slice(1).toLowerCase();
}
