"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "../client";
import { qk } from "../keys";
import { useAuthedQueryOptions } from "./shared";

/**
 * The directory reads that a client island still makes. Searching, the facet
 * lists and a member's career path are all fetched on the server now, by the
 * loaders in `api/server.ts`, so they have no hook here.
 */
export function useMember(slug: string | null) {
    const gate = useAuthedQueryOptions();
    return useQuery({
        queryKey: qk.member(slug ?? ""),
        queryFn: () =>
            unwrap(api.GET("/api/v1/members/{slug}", { params: { path: { slug: slug! } } })),
        ...gate,
        enabled: gate.enabled && Boolean(slug),
    });
}
