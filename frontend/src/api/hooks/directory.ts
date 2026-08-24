"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "../client";
import { qk } from "../keys";
import type { MembersPage } from "../types";
import { useAuthedQueryOptions } from "./shared";

/**
 * The plain directory search: type a name (or a company, a study, a place) and
 * get the people back. This is the keyword counterpart to Ask, for when you
 * already know who you are looking for and just want to find them by name.
 *
 * An empty query returns the first page of everyone, so the directory has
 * something to show before a single key is pressed.
 */
export function useMemberSearch(q: string) {
    const gate = useAuthedQueryOptions();
    const query = { q: q.trim() || undefined, limit: 40 } as const;
    return useQuery<MembersPage>({
        queryKey: qk.members(query),
        queryFn: () => unwrap(api.GET("/api/v1/members/", { params: { query } })),
        ...gate,
    });
}
