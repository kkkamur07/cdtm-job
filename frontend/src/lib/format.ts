/** Display helpers shared by the community and job board screens. */

/** snake_case enum values from the API read as words in the UI. */
export function humanise(value: string | null | undefined): string {
    if (!value) return "";
    return value.replaceAll("_", " ");
}

/**
 * Enum values as a badge reads them.
 *
 * `humanise` alone gives "full time" and "working student", which look like
 * typos next to "Hybrid" and "Senior". The exceptions are the compounds English
 * hyphenates; everything else is sentence case.
 */
const BADGE_WORDS: Record<string, string> = {
    full_time: "Full-time",
    part_time: "Part-time",
    working_student: "Working student",
    freelance: "Freelance",
    internship: "Internship",
    contract: "Contract",
    temporary: "Temporary",
    onsite: "Onsite",
    remote: "Remote",
    hybrid: "Hybrid",
    intern: "Intern",
    entry: "Entry",
    mid: "Mid",
    senior: "Senior",
    lead: "Lead",
};

export function badgeLabel(value: string | null | undefined): string {
    if (!value) return "";
    const known = BADGE_WORDS[value];
    if (known) return known;
    const words = humanise(value);
    return words.charAt(0).toUpperCase() + words.slice(1);
}

export function initials(name: string): string {
    const parts = name.split(/\s+/).filter((p) => /[a-zA-ZÀ-ɏ]/.test(p));
    if (!parts.length) return "?";
    const first = parts[0][0] ?? "";
    const last = parts.length > 1 ? (parts[parts.length - 1][0] ?? "") : "";
    return (first + last).toUpperCase();
}

export function firstName(name: string): string {
    return name.split(/\s+/)[0] ?? name;
}

/**
 * Every date is formatted in one fixed zone and locale.
 *
 * These strings are produced on the server and then hydrated in the browser. If
 * the two disagree about the time zone, React reports a hydration mismatch and
 * the date visibly changes after load, so the zone is stated rather than
 * inherited from whatever machine is rendering.
 */
const ZONE = "Europe/Berlin";
const LOCALE = "en-GB";

function parse(value: string | null | undefined): Date | null {
    if (!value) return null;
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDate(value: string | null | undefined): string | null {
    const date = parse(value);
    if (!date) return null;
    return date.toLocaleDateString(LOCALE, {
        day: "numeric",
        month: "short",
        year: "numeric",
        timeZone: ZONE,
    });
}

export function formatDateTime(value: string | null | undefined): string | null {
    const date = parse(value);
    if (!date) return null;
    return date.toLocaleString(LOCALE, {
        weekday: "short",
        day: "numeric",
        month: "short",
        hour: "2-digit",
        minute: "2-digit",
        timeZone: ZONE,
    });
}

/** Big day number plus month, for the date block on event rows. */
export function dateParts(value: string | null | undefined): { day: string; month: string } | null {
    const date = parse(value);
    if (!date) return null;
    return {
        day: date.toLocaleDateString(LOCALE, { day: "numeric", timeZone: ZONE }),
        month: date.toLocaleDateString(LOCALE, { month: "short", timeZone: ZONE }).toUpperCase(),
    };
}

export function timeAgo(value: string | null | undefined): string | null {
    const date = parse(value);
    if (!date) return null;
    const days = Math.floor((Date.now() - date.getTime()) / 86_400_000);
    if (days < 0) return formatDate(value);
    if (days === 0) return "Today";
    if (days === 1) return "Yesterday";
    if (days < 7) return `${days} days ago`;
    if (days < 14) return "1 week ago";
    if (days < 60) return `${Math.floor(days / 7)} weeks ago`;
    return formatDate(value);
}

/** Salary lines are optional at every level, so this returns null a lot. */
export function formatSalary(job: {
    salary_min?: string | null;
    salary_max?: string | null;
    salary_currency?: string | null;
    salary_period?: string | null;
    compensation_disclosure?: string | null;
}): string | null {
    if (job.compensation_disclosure && job.compensation_disclosure !== "public") return null;
    const min = job.salary_min ? Number(job.salary_min) : null;
    const max = job.salary_max ? Number(job.salary_max) : null;
    if (min === null && max === null) return null;

    const currency = job.salary_currency ?? "EUR";
    const fmt = (n: number) =>
        new Intl.NumberFormat(LOCALE, {
            style: "currency",
            currency,
            maximumFractionDigits: 0,
        }).format(n);

    const range = min !== null && max !== null ? `${fmt(min)} - ${fmt(max)}` : fmt((min ?? max)!);
    const period = job.salary_period === "yearly" ? "per year" : humanise(job.salary_period);
    return period ? `${range} ${period}` : range;
}

const CURRENCY_SIGNS: Record<string, string> = { EUR: "€", USD: "$", GBP: "£", CHF: "CHF" };

function sign(currency: string | null | undefined): string {
    const code = (currency ?? "EUR").toUpperCase();
    return CURRENCY_SIGNS[code] ?? code;
}

/**
 * The short salary a listing row shows: "€ 85 to 105k", not
 * "€85,000 - €105,000 per year".
 *
 * A row is scanned, not read, and three roles' worth of full currency
 * formatting is a wall of digits. The detail page keeps `formatSalary`, which
 * spells it out.
 */
export function compactSalary(job: {
    salary_min?: string | null;
    salary_max?: string | null;
    salary_currency?: string | null;
    salary_period?: string | null;
    compensation_disclosure?: string | null;
}): string | null {
    if (job.compensation_disclosure && job.compensation_disclosure !== "public") return null;
    const min = job.salary_min ? Number(job.salary_min) : null;
    const max = job.salary_max ? Number(job.salary_max) : null;
    if (min === null && max === null) return null;

    const symbol = sign(job.salary_currency);
    const thousands = (n: number) => `${Math.round(n / 1000)}k`;

    if (job.salary_period === "hourly" || job.salary_period === "monthly") {
        const value = new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 }).format(
            (min ?? max)!,
        );
        return `${symbol} ${value} per ${job.salary_period === "hourly" ? "hour" : "month"}`;
    }

    if (min !== null && max !== null) return `${symbol} ${Math.round(min / 1000)} to ${thousands(max)}`;
    return `${symbol} ${thousands((min ?? max)!)}`;
}

/** Rent, in the form the housing cards use: "€ 720". */
export function formatPrice(value: number | string | null | undefined): string | null {
    if (value === null || value === undefined || value === "") return null;
    const amount = Number(value);
    if (Number.isNaN(amount)) return null;
    return `€ ${new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 }).format(amount)}`;
}

/**
 * "1 Oct to 31 Mar", with the year only where it is not obvious.
 *
 * A range inside the next twelve months does not need the year on either end;
 * one that crosses further out keeps it, so "1 Oct 2027" cannot be mistaken for
 * this October.
 */
export function dateRange(
    from: string | null | undefined,
    until: string | null | undefined,
): string | null {
    const start = parse(from);
    const end = parse(until);
    if (!start && !end) return null;

    const thisYear = new Date().getFullYear();
    const short = (date: Date) =>
        date.toLocaleDateString(LOCALE, {
            day: "numeric",
            month: "short",
            timeZone: ZONE,
            ...(date.getFullYear() === thisYear ? {} : { year: "numeric" }),
        });

    if (start && end) return `${short(start)} to ${short(end)}`;
    if (start) return `From ${short(start)}`;
    return `Until ${short(end!)}`;
}

/** "1 room" and "2 rooms", never "1.0 rooms". */
export function roomsLabel(rooms: number | string | null | undefined): string | null {
    if (rooms === null || rooms === undefined || rooms === "") return null;
    const count = Number(rooms);
    if (Number.isNaN(count)) return null;
    const shown = Number.isInteger(count) ? String(count) : String(count);
    return `${shown} ${count === 1 ? "room" : "rooms"}`;
}

const ALLOWED_PROTOCOLS = new Set(["http:", "https:", "mailto:"]);

/** Never render an href we have not vetted: listing URLs are supplied by Members. */
export function safeUrl(url: string | null | undefined): string | null {
    if (!url) return null;
    const trimmed = url.trim();
    try {
        return ALLOWED_PROTOCOLS.has(new URL(trimmed).protocol) ? trimmed : null;
    } catch {
        return null;
    }
}

/** URL-safe slug; max length matches the API `slug` field. */
export function slugify(input: string, maxLen = 128): string {
    return input
        .trim()
        .toLowerCase()
        .normalize("NFKD")
        .replace(/[̀-ͯ]/g, "")
        .replace(/[^\w\s-]/g, "")
        .replace(/\s+/g, "-")
        .replace(/-+/g, "-")
        .replace(/^-|-$/g, "")
        .slice(0, maxLen);
}

/**
 * Comma separated text to a list and back. Topics, hobbies and skill lists are
 * short and typed by hand, so a plain field beats a tag widget: it is
 * keyboard-native, pastes from anywhere, and has nothing to learn.
 */
export function parseList(value: string): string[] {
    return value
        .split(",")
        .map((item) => item.trim())
        .filter(Boolean);
}

export function joinList(items: string[] | null | undefined): string {
    return (items ?? []).join(", ");
}

/**
 * Today's weekday, in the same locale and timezone as every other date here.
 *
 * The greeting on the home page used to call `toLocaleDateString("en-GB", ...)`
 * inline, which quietly forked the app's date formatting into two places and
 * left the weekday on the server's timezone rather than Munich's.
 */
export function weekdayName(date: Date = new Date()): string {
    return date.toLocaleDateString(LOCALE, { weekday: "long", timeZone: ZONE });
}

/**
 * Free text split into paragraphs, each with a key that survives a re-render.
 *
 * The key is the character offset the paragraph starts at, not its position in
 * the array, so two identical paragraphs still get different keys and nothing
 * shifts if the text is edited above them.
 */
export function paragraphs(text: string): { key: string; text: string }[] {
    let offset = 0;
    const parts: { key: string; text: string }[] = [];
    for (const part of text.split(/\n{2,}/)) {
        parts.push({ key: `p${offset}`, text: part });
        offset += part.length + 2;
    }
    return parts;
}
