"use server";

import { redirect } from "next/navigation";

import {
  createCompanyApiV1CompaniesPost,
  createJobApiV1JobsPost,
} from "@/lib/api/generated";
import type {
  CompanyCreate,
  CompanySizeBand,
  EmploymentType,
  ExperienceLevel,
  JobCreate,
  WorkArrangement,
} from "@/lib/api/generated";
import { getApiClient } from "@/lib/api/get-client";
import { slugify } from "@/lib/slug";

export type PostJobActionState = { error?: string } | null;

function str(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

function optionalUrl(formData: FormData, key: string): string | null {
  const v = str(formData, key);
  return v || null;
}

export async function postJobAction(
  _prev: PostJobActionState,
  formData: FormData,
): Promise<PostJobActionState> {
  const companySource = str(formData, "company_source");
  const client = getApiClient();

  let company_id: string;

  if (companySource === "new") {
    const name = str(formData, "new_company_name");
    if (!name) {
      return { error: "Company name is required when creating a new company." };
    }
    let slug = str(formData, "new_company_slug");
    slug = slugify(slug || name);
    if (!slug) {
      return { error: "Could not build a URL slug; try a different company name or slug." };
    }

    const sizeRaw = str(formData, "new_company_size_band");
    const company_size_band: CompanySizeBand | null =
      sizeRaw === "startup" || sizeRaw === "smb" || sizeRaw === "mid" || sizeRaw === "enterprise"
        ? sizeRaw
        : null;

    const companyBody: CompanyCreate = {
      name,
      slug,
      short_description: str(formData, "new_company_short_description") || null,
      website_url: optionalUrl(formData, "new_company_website"),
      industry: str(formData, "new_company_industry") || null,
      hq_city: str(formData, "new_company_hq_city") || null,
      company_size_band,
      is_cdtm_startup: formData.get("new_company_is_cdtm_startup") === "on",
    };

    const companyRes = await createCompanyApiV1CompaniesPost({ client, body: companyBody });
    if (companyRes.error || !companyRes.data) {
      return {
        error:
          "Could not create the company (slug may already exist). Adjust the slug and try again.",
      };
    }
    company_id = companyRes.data.id;
  } else {
    company_id = str(formData, "company_id");
    if (!company_id) {
      return { error: "Select a company, or switch to “New company” to create one." };
    }
  }

  const title = str(formData, "title");
  const description = str(formData, "description");
  const employment_type = str(formData, "employment_type") as EmploymentType;
  const work_arrangement = str(formData, "work_arrangement") as WorkArrangement;
  const experience_level = str(formData, "experience_level") as ExperienceLevel;

  if (!title || !description) {
    return { error: "Title and description are required." };
  }

  const jobBody: JobCreate = {
    company_id,
    title,
    description,
    employment_type,
    work_arrangement,
    experience_level,
    status: "published",
    summary: str(formData, "summary") || null,
    location_display: str(formData, "location_display") || null,
    application_url: optionalUrl(formData, "application_url"),
    application_email: str(formData, "application_email") || null,
  };

  const jobRes = await createJobApiV1JobsPost({ client, body: jobBody });
  if (jobRes.error || !jobRes.data) {
    return { error: "Could not publish the job. Check the form and try again." };
  }

  redirect(`/jobs/${jobRes.data.id}`);
}
