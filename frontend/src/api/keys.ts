/**
 * Every React Query key in one place. Mutations invalidate by prefix, so the
 * shapes here decide what refetches after a write.
 */
export const qk = {
    /** Roster type-ahead on the dev sign-in screen. Unauthenticated. */
    devMembers: (query: string) => ["auth", "dev-members", query] as const,

    me: ["me"] as const,
    myMember: ["me", "member"] as const,
    myEntry: ["me", "entry"] as const,
    myIntents: ["me", "intents"] as const,
    mySaved: ["me", "saved"] as const,
    myIntros: ["me", "intros"] as const,

    members: (params: unknown) => ["members", params] as const,
    memberFacets: ["members", "facets"] as const,
    member: (slug: string) => ["member", slug] as const,
    memberPath: (slug: string) => ["member", slug, "path"] as const,

    events: (upcoming: boolean) => ["events", { upcoming }] as const,
    event: (id: string) => ["event", id] as const,

    /**
     * Prefix for everything announcement-shaped. Lists are keyed by the page
     * size they were fetched with, so the two-item home widget and the full
     * board never seed each other's cache with the wrong number of rows.
     */
    announcements: ["announcements"] as const,
    announcementList: (limit: number) => ["announcements", "list", limit] as const,

    /**
     * Lists and details sit under `["housing"]` but in separate branches, so a
     * write can invalidate the boards without also throwing away every cached
     * listing. Writes invalidate `["housing", "list"]`, plus the one detail
     * they touched.
     */
    housing: (params: unknown) => ["housing", "list", params] as const,
    housingListing: (id: string) => ["housing", "detail", id] as const,

    pathsFlow: (params: unknown) => ["paths", "flow", params] as const,
    pathsGroups: ["paths", "groups"] as const,
    pathsMembers: (params: unknown) => ["paths", "members", params] as const,

    jobs: (params: unknown) => ["jobs", params] as const,
    job: (slug: string) => ["job", slug] as const,
    companies: (params: unknown) => ["companies", params] as const,
    company: (id: string) => ["company", id] as const,
} as const;
