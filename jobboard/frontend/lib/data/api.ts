import { cache } from "react";

import { getApiClient } from "@/lib/api/get-client";
import {
  getCompanyApiV1CompaniesCompanyIdGet,
  getCompanyBySlugApiV1CompaniesSlugSlugGet,
  getJobApiV1JobsJobIdGet,
  getSeekerApiV1SeekersSeekerIdGet,
  listCompaniesApiV1CompaniesGet,
  listJobsApiV1JobsGet,
  listSeekersApiV1SeekersGet,
} from "@/lib/api/generated";
import type {
  CompaniesPublic,
  CompanyPublic,
  JobPublic,
  JobsPublic,
  SeekerPublic,
  SeekersPublic,
} from "@/lib/api/generated";

const PAGE_SIZE = 100;

async function fetchAllPages<T>(
  fetchPage: (skip: number, limit: number) => Promise<{ items: T[]; total: number }>,
): Promise<{ items: T[]; total: number }> {
  const first = await fetchPage(0, PAGE_SIZE);
  if (first.items.length >= first.total) {
    return first;
  }

  const items = [...first.items];
  for (let skip = PAGE_SIZE; skip < first.total; skip += PAGE_SIZE) {
    const page = await fetchPage(skip, PAGE_SIZE);
    items.push(...page.items);
  }
  return { items, total: first.total };
}

export const fetchPublishedJobs = cache(async (): Promise<JobsPublic> => {
  const client = getApiClient();
  return fetchAllPages(async (skip, limit) => {
    const { data } = await listJobsApiV1JobsGet({
      client,
      query: { status: "published", skip, limit },
      throwOnError: true,
    });
    return data;
  });
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

export const fetchCompany = cache(async (companyId: string): Promise<CompanyPublic> => {
  const client = getApiClient();
  const { data } = await getCompanyApiV1CompaniesCompanyIdGet({
    client,
    path: { company_id: companyId },
    throwOnError: true,
  });
  return data;
});

export const fetchCompanies = cache(async (): Promise<CompaniesPublic> => {
  const client = getApiClient();
  return fetchAllPages(async (skip, limit) => {
    const { data } = await listCompaniesApiV1CompaniesGet({
      client,
      query: { skip, limit },
      throwOnError: true,
    });
    return data;
  });
});

export const fetchCompanyBySlug = cache(async (slug: string): Promise<CompanyPublic> => {
  const client = getApiClient();
  const { data } = await getCompanyBySlugApiV1CompaniesSlugSlugGet({
    client,
    path: { slug },
    throwOnError: true,
  });
  return data;
});

export const fetchPublishedJobsForCompany = cache(
  async (companyId: string): Promise<JobsPublic> => {
    const client = getApiClient();
    return fetchAllPages(async (skip, limit) => {
      const { data } = await listJobsApiV1JobsGet({
        client,
        query: { company_id: companyId, status: "published", skip, limit },
        throwOnError: true,
      });
      return data;
    });
  },
);

export const fetchSeekers = cache(async (): Promise<SeekersPublic> => {
  const client = getApiClient();
  return fetchAllPages(async (skip, limit) => {
    const { data } = await listSeekersApiV1SeekersGet({
      client,
      query: { skip, limit },
      throwOnError: true,
    });
    return data;
  });
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
