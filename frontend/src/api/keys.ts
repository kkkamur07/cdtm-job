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

    /**
     * The shortlist in two shapes, because two different questions are asked of
     * it. `mySaved` is the page of cards `/me` reads; `mySavedIds` is the bare
     * id set every Save button reads. `mySaved` doubles as the prefix over both,
     * so one invalidation after a write refreshes each of them.
     */
    mySaved: ["me", "saved"] as const,
    mySavedIds: ["me", "saved", "ids"] as const,

    /**
     * Intro requests. `myIntros` is the prefix a write invalidates; the lists
     * under it are keyed by who they were narrowed to, so a profile asking
     * about one member and the inbox showing everything do not overwrite each
     * other's page.
     */
    myIntros: ["me", "intros"] as const,
    myIntrosList: (withMemberId?: string) => ["me", "intros", withMemberId ?? "all"] as const,

    members: (params: unknown) => ["members", params] as const,
    memberFacets: ["members", "facets"] as const,
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
     * listing. `housingLists` is the prefix a write invalidates, alongside the
     * one detail it touched.
     *
     * The boards themselves are rendered on the server and filtered in the
     * browser, so nothing holds a list under this prefix yet; the invalidation
     * is what keeps that true the day one does.
     */
    housingLists: ["housing", "list"] as const,
    housingListing: (id: string) => ["housing", "detail", id] as const,

    pathsFlow: (params: unknown) => ["paths", "flow", params] as const,
    pathsGroups: ["paths", "groups"] as const,
    pathsMembers: (params: unknown) => ["paths", "members", params] as const,

    job: (slug: string) => ["job", slug] as const,
    companies: (params: unknown) => ["companies", params] as const,
    company: (id: string) => ["company", id] as const,
} as const;
