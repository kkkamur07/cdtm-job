"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api, unwrap } from "../client";
import { qk } from "../keys";
import type { CompanyCreate, JobCreate } from "../types";
import { usePublicQueryOptions } from "./shared";

/**
 * Jobs and companies read without a token, so these hooks do not wait on the
 * session. Posting a job or creating a company does need one, and the backend
 * says so with a 403 the form surfaces.
 *
 * Only the company type-ahead reads from the browser. The job board itself is
 * loaded on the server and filtered client-side, so the job hooks here are the
 * writes.
 */

export function useCreateJob() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: JobCreate) => unwrap(api.POST("/api/v1/jobs/", { body })),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["jobs"] }),
    });
}

export function useCompanies(params: { q?: string; limit?: number } = {}) {
    return useQuery({
        queryKey: qk.companies(params),
        queryFn: () =>
            unwrap(api.GET("/api/v1/companies/", { params: { query: { limit: 100, ...params } } })),
        ...usePublicQueryOptions(),
        placeholderData: (previous) => previous,
    });
}

export function useCreateCompany() {
    const qc = useQueryClient();
    return useMutation({
        mutationFn: (body: CompanyCreate) => unwrap(api.POST("/api/v1/companies/", { body })),
        onSuccess: () => qc.invalidateQueries({ queryKey: ["companies"] }),
    });
}
