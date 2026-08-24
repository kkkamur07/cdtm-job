import "server-only";

import { cache } from "react";

import { API_BASE_URL, API_PREFIX } from "./config";
import { toApiError } from "./errors";
import { getAccessToken } from "@/auth/session";
import type {
    Announcement,
    Company,
    CompanyContact,
    CommunityEvent,
    CommunityEventSummary,
    DirectoryFacets,
    HousingListing,
    HousingListingSummary,
    Intents,
    Job,
    JobSummary,
    Me,
    Member,
    MemberPath,
    MemberProfile,
    PathFlow,
    PathGroups,
    SavedMembersPage,
} from "./types";

/**
 * Server-side reads.
 *
 * Two rules shape this file. Every loader is wrapped in `React.cache`, so a
 * page and its children asking for the same thing costs one request per render
 * rather than one per component. And nothing is held at module scope: the
 * bearer token comes from the request's own cookies each time, because a shared
 * module variable would leak one visitor's session into another's render.
 *
 * Callers fetch independent things with `Promise.all`. Awaiting them one after
 * another is the waterfall this layer exists to avoid.
 */

type Query = Record<string, string | number | boolean | string[] | undefined | null>;

async function get<T>(path: string, query?: Query, options?: { revalidate?: number }): Promise<T> {
    const url = new URL(`${API_PREFIX}${path}`, API_BASE_URL);
    for (const [key, value] of Object.entries(query ?? {})) {
        if (value === undefined || value === null || value === "") continue;
        if (Array.isArray(value)) {
            for (const item of value) url.searchParams.append(key, item);
        } else {
            url.searchParams.set(key, String(value));
        }
    }

    const accessToken = await getAccessToken();
    const headers: HeadersInit = { Accept: "application/json" };
    if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

    const response = await fetch(url, {
        headers,
        // Anything personalised must never be cached across visitors. Public
        // reads opt in explicitly with a revalidate window.
        ...(accessToken || options?.revalidate === undefined
            ? { cache: "no-store" as const }
            : { next: { revalidate: options.revalidate } }),
    });

    if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw toApiError(response, body);
    }
    return (await response.json()) as T;
}

type Page<T> = { items: T[]; total: number };

/* ------------------------------------------------------------------ me */

export const loadMe = cache(() => get<Me>("/auth/me"));
export const loadMyMember = cache(() => get<MemberProfile>("/members/me"));
export const loadMyIntents = cache(() => get<Intents | null>("/members/me/intents"));
/**
 * The shortlist, as a page.
 *
 * `/network/saved` is `{items, total}` like every other list now, and 100 is the cap
 * `PageParams` allows. The home feed and `/me` both want the whole shortlist rather than
 * a window on it, so they ask for the first hundred and read `total` for the count; a
 * member with more than a hundred saved people would see the hundred most recent.
 */
export const loadMySaved = cache(() => get<SavedMembersPage>("/network/saved", { limit: 100 }));

/* ------------------------------------------------------------- members */

export const loadMembers = cache((query: Query) =>
    get<Page<Member>>("/members/", query),
);
export const loadFacets = cache(() => get<DirectoryFacets>("/members/facets"));
export const loadMember = cache((slug: string) =>
    get<MemberProfile>(`/members/${encodeURIComponent(slug)}`),
);

/* ----------------------------------------------------------- community */

/** The board reads fifty; the home widget asks for the two it shows. */
export const loadAnnouncements = cache((limit = 50) =>
    get<Page<Announcement> & { unread: number }>("/announcements/", { limit }),
);

/**
 * Just the badge number.
 *
 * The shell used to read it off `loadAnnouncements`, which meant every page in
 * the app pulled fifty announcements with their full bodies over the wire to
 * take one integer off the envelope. Dropping that call to `limit: 1` would not
 * have helped: `React.cache` keys on the argument, so the shell and the
 * announcements page would then have made two requests where they now make
 * one. A count of its own is the only shape that is a win on every route.
 */
export const loadUnreadCount = cache(() => get<{ unread: number }>("/announcements/unread-count"));
export const loadEvents = cache((upcoming: boolean) =>
    get<Page<CommunityEventSummary>>("/events/", { upcoming, limit: 100 }),
);
export const loadEvent = cache((id: string) =>
    get<CommunityEvent>(`/events/${encodeURIComponent(id)}`),
);
export const loadHousing = cache((query: Query) =>
    get<Page<HousingListingSummary>>("/housing/", query),
);
export const loadHousingListing = cache((id: string) =>
    get<HousingListing>(`/housing/${encodeURIComponent(id)}`),
);

/* --------------------------------------------------------------- paths */

/**
 * One member's three-step path. It used to ride along on the profile; it is a
 * separate read now, so the page fetches it alongside the profile rather than
 * after it.
 */
export const loadMemberPath = cache((slug: string) =>
    get<MemberPath>(`/paths/members/${encodeURIComponent(slug)}`),
);

export const loadPathFlow = cache((query: Query) => get<PathFlow>("/paths/flow", query));
export const loadPathGroups = cache(() => get<PathGroups>("/paths/groups"));
export const loadPathMembers = cache((query: Query) =>
    get<Page<Member>>("/paths/members", query),
);

/* ------------------------------------------------------------ jobboard */

export const loadJobs = cache((query: Query) =>
    get<Page<JobSummary>>("/jobs/", query, { revalidate: 60 }),
);
export const loadJobBySlug = cache((slug: string) =>
    get<Job>(`/jobs/slug/${encodeURIComponent(slug)}`, undefined, { revalidate: 60 }),
);
export const loadJob = cache((id: string) =>
    get<Job>(`/jobs/${encodeURIComponent(id)}`, undefined, { revalidate: 60 }),
);

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/**
 * A job's URL segment is its slug, except that `slug` is nullable, in which
 * case the board links by id. Both arrive at the same route, so the shape of
 * the segment decides which endpoint answers it rather than a failed request
 * followed by a retry.
 */
export function loadJobByRef(ref: string): Promise<Job> {
    return UUID.test(ref) ? loadJob(ref) : loadJobBySlug(ref);
}
export const loadCompanies = cache((query: Query) =>
    get<Page<Company>>("/companies/", query, { revalidate: 300 }),
);
export const loadCompany = cache((id: string) =>
    get<Company>(`/companies/${encodeURIComponent(id)}`, undefined, { revalidate: 300 }),
);

/**
 * Members by id, for the ids a page actually shows.
 *
 * Jobs, housing listings, events and announcements all reference their author
 * as a bare `*_member_id`. `GET /members/lookup` resolves up to fifty
 * of those per call, so a page that lists twenty rows costs one request instead
 * of the eleven pages of directory this used to hold.
 *
 * Callers pass the ids they have, nulls included; the filtering and de-duping
 * happens here so no screen has to remember to do it.
 */
const LOOKUP_BATCH = 50;

/**
 * `React.cache` compares arguments by identity, and every caller builds a fresh
 * array, so the cached function takes the ids as one sorted string. Two
 * components asking for the same set then share a request.
 */
const lookupMembers = cache(async (key: string): Promise<Map<string, Member>> => {
    const wanted = key ? key.split(",") : [];
    const index = new Map<string, Member>();
    if (!wanted.length) return index;

    const batches: string[][] = [];
    for (let start = 0; start < wanted.length; start += LOOKUP_BATCH) {
        batches.push(wanted.slice(start, start + LOOKUP_BATCH));
    }

    // Batches are independent, so they go out together rather than in turn.
    const pages = await Promise.all(
        batches.map((batch) => get<Page<Member>>("/members/lookup", { ids: batch })),
    );
    for (const page of pages) {
        for (const member of page.items) index.set(member.id, member);
    }
    return index;
});

/**
 * One CDTM member per company name, for a board that lists many companies.
 *
 * The point of the job board is that there is usually somebody inside you can
 * ask before you apply, which used to cost one `/members?company=<name>` request
 * per row. This endpoint takes up to fifty names at once and echoes each one
 * back exactly as sent, so the answer keys straight onto the rows.
 *
 * Same `React.cache` trick as the member lookup: the key is the sorted names as
 * one string, because a fresh array would miss the cache every time.
 */
const AT_COMPANY_LIMIT = 50;

const membersAtCompanies = cache(async (key: string): Promise<Map<string, Member>> => {
    const names = key ? key.split("\n") : [];
    const found = new Map<string, Member>();
    if (!names.length) return found;

    const batches: string[][] = [];
    for (let start = 0; start < names.length; start += AT_COMPANY_LIMIT) {
        batches.push(names.slice(start, start + AT_COMPANY_LIMIT));
    }

    const pages = await Promise.all(
        batches.map((batch) =>
            get<{ items: CompanyContact[]; total: number }>("/members/at-company", {
                company: batch,
            }),
        ),
    );
    for (const page of pages) {
        for (const contact of page.items) found.set(contact.company, contact.member);
    }
    return found;
});

/** Names with no member are simply absent from the map. */
export function loadMembersAtCompanies(
    names: readonly (string | null | undefined)[],
): Promise<Map<string, Member>> {
    const wanted = [...new Set(names.filter((name): name is string => Boolean(name)))].sort();
    return membersAtCompanies(wanted.join("\n"));
}

export function loadMemberIndex(
    ids: readonly (string | null | undefined)[],
): Promise<Map<string, Member>> {
    const wanted = [...new Set(ids.filter((id): id is string => Boolean(id)))].sort();
    return lookupMembers(wanted.join(","));
}
