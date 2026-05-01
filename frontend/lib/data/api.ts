import { cache } from "react";

import { getApiClient } from "@/lib/api/get-client";
import {
  getJobApiV1JobsJobIdGet,
  getSeekerApiV1SeekersSeekerIdGet,
  listCompaniesApiV1CompaniesGet,
  listJobsApiV1JobsGet,
  listSeekersApiV1SeekersGet,
} from "@/lib/api/generated";
import type {
  CompaniesPublic,
  JobPublic,
  JobsPublic,
  SeekerPublic,
  SeekersPublic,
} from "@/lib/api/generated";

export const fetchPublishedJobs = cache(async (): Promise<JobsPublic> => {
  const client = getApiClient();
  const { data } = await listJobsApiV1JobsGet({
    client,
    query: { status: "published", limit: 100 },
    throwOnError: true,
  });
  return data;
});

export const fetchJob = cache(async (jobId: string): Promise<JobPublic> => {
  const client = getApiClient();
  const { data } = await getJobApiV1JobsJobIdGet({
    client,
    path: { job_id: jobId },
    throwOnError: true,
  });
  return data;
});

export const fetchCompanies = cache(async (): Promise<CompaniesPublic> => {
  const client = getApiClient();
  const { data } = await listCompaniesApiV1CompaniesGet({
    client,
    query: { limit: 100 },
    throwOnError: true,
  });
  return data;
});

export const fetchSeekers = cache(async (): Promise<SeekersPublic> => {
  const client = getApiClient();
  const { data } = await listSeekersApiV1SeekersGet({
    client,
    query: { limit: 100 },
    throwOnError: true,
  });
  return data;
});

export const fetchSeeker = cache(async (seekerId: string): Promise<SeekerPublic> => {
  const client = getApiClient();
  const { data } = await getSeekerApiV1SeekersSeekerIdGet({
    client,
    path: { seeker_id: seekerId },
    throwOnError: true,
  });
  return data;
});
