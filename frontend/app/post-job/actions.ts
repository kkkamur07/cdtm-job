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
import { formString, optionalHttpUrl } from "@/lib/form-data";
import { slugify } from "@/lib/slug";

export type PostJobActionState = { error?: string } | null;

export async function postJobAction(
  _prev: PostJobActionState,
  formData: FormData,
): Promise<PostJobActionState> {
  const companySource = formString(formData, "company_source");
  const client = getApiClient();

  let company_id: string;

  if (companySource === "new") {
    const name = formString(formData, "new_company_name");
    if (!name) {
      return { error: "Company name is required when creating a new company." };
    }
    let slug = formString(formData, "new_company_slug");
    slug = slugify(slug || name);
    if (!slug) {
      return { error: "Could not build a URL slug; try a different company name or slug." };
    }

    const sizeRaw = formString(formData, "new_company_size_band");
    const company_size_band: CompanySizeBand | null =
      sizeRaw === "startup" || sizeRaw === "smb" || sizeRaw === "mid" || sizeRaw === "enterprise"
        ? sizeRaw
        : null;

    const companyBody: CompanyCreate = {
      name,
      slug,
      short_description: formString(formData, "new_company_short_description") || null,
      website_url: optionalHttpUrl(formData, "new_company_website"),
      industry: formString(formData, "new_company_industry") || null,
      hq_city: formString(formData, "new_company_hq_city") || null,
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
    company_id = formString(formData, "company_id");
    if (!company_id) {
      return { error: "Select a company, or switch to “New company” to create one." };
    }
  }

  const title = formString(formData, "title");
  const description = formString(formData, "description");
  const employment_type = formString(formData, "employment_type") as EmploymentType;
  const work_arrangement = formString(formData, "work_arrangement") as WorkArrangement;
  const experience_level = formString(formData, "experience_level") as ExperienceLevel;

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
    summary: formString(formData, "summary") || null,
    location_display: formString(formData, "location_display") || null,
    application_url: optionalHttpUrl(formData, "application_url"),
    application_email: formString(formData, "application_email") || null,
  };

  const jobRes = await createJobApiV1JobsPost({ client, body: jobBody });
  if (jobRes.error || !jobRes.data) {
    return { error: "Could not publish the job. Check the form and try again." };
  }

  redirect(`/jobs/${jobRes.data.id}`);
}
