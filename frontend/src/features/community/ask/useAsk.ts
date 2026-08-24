"use client";

import { useQuery } from "@tanstack/react-query";

import { api, unwrap } from "@/api/client";
import { ApiError } from "@/api/errors";
import { useAuthedQueryOptions } from "@/api/hooks/shared";
import type { AskAnswer, HousingAskAnswer, JobAskAnswer } from "./types";

/**
 * Asking a question.
 *
 * The three Ask endpoints are POSTs, but a question is a read: the same words
 * give the same answer, and going back to a question should not spend another
 * model call. So they are queries keyed on the question rather than mutations,
 * and `placeholderData` keeps the previous answer on screen while the next one
 * is being interpreted instead of blanking the page.
 *
 * A 404 means this deployment's backend does not serve Ask yet. That is not an
 * error worth retrying, and the callers show a "warming up" line for it, so it
 * is surfaced as `notReady` rather than as a failure.
 */

const MIN_LENGTH = 3;

type Common = { enabled?: boolean; limit?: number };

function askOptions(gate: ReturnType<typeof useAuthedQueryOptions>, question: string, enabled: boolean) {
    return {
        ...gate,
        enabled: gate.enabled && enabled && question.trim().length >= MIN_LENGTH,
        placeholderData: <T,>(previous: T) => previous,
        staleTime: 5 * 60 * 1000,
        retry: (failureCount: number, error: Error) => {
            if (error instanceof ApiError && (error.isAuth || error.isForbidden || error.isNotFound)) {
                return false;
            }
            return failureCount < 1;
        },
    };
}

/** True when the failure is "this backend has no Ask yet", not "Ask broke". */
export function isNotReady(error: unknown): boolean {
    return error instanceof ApiError && error.isNotFound;
}

export function useAsk(question: string, { enabled = true, limit = 24 }: Common = {}) {
    const gate = useAuthedQueryOptions();
    const trimmed = question.trim();
    return useQuery<AskAnswer>({
        queryKey: ["ask", "community", trimmed, limit],
        queryFn: () =>
            unwrap(api.POST("/api/v1/members/ask/", { body: { question: trimmed, skip: 0, limit } })),
        ...askOptions(gate, trimmed, enabled),
    });
}

export function useJobAsk(question: string, { enabled = true, limit = 40 }: Common = {}) {
    const gate = useAuthedQueryOptions();
    const trimmed = question.trim();
    return useQuery<JobAskAnswer>({
        queryKey: ["ask", "jobs", trimmed, limit],
        queryFn: () => unwrap(api.POST("/api/v1/jobs/ask/", { body: { question: trimmed, skip: 0, limit } })),
        ...askOptions(gate, trimmed, enabled),
    });
}

export function useHousingAsk(question: string, { enabled = true, limit = 40 }: Common = {}) {
    const gate = useAuthedQueryOptions();
    const trimmed = question.trim();
    return useQuery<HousingAskAnswer>({
        queryKey: ["ask", "housing", trimmed, limit],
        queryFn: () =>
            unwrap(
                api.POST("/api/v1/housing/ask/", { body: { question: trimmed, skip: 0, limit } }),
            ),
        ...askOptions(gate, trimmed, enabled),
    });
}
