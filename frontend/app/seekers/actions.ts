"use server";

import { redirect } from "next/navigation";

import { createSeekerApiV1SeekersPost } from "@/lib/api/generated";
import type { SeekerCreate } from "@/lib/api/generated";
import { getApiClient } from "@/lib/api/get-client";
import { formString, optionalHttpUrl } from "@/lib/form-data";

export type SeekerActionState = { error?: string } | null;

function splitList(raw: string): string[] {
  return raw
    .split(/[,;\n]+/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export async function createSeekerAction(
  _prev: SeekerActionState,
  formData: FormData,
): Promise<SeekerActionState> {
  const full_name = formString(formData, "full_name");
  if (!full_name) {
    return { error: "Name is required." };
  }

  const body: SeekerCreate = {
    full_name,
    email: formString(formData, "email") || null,
    headline: formString(formData, "headline") || null,
    bio: formString(formData, "bio") || null,
    linkedin_url: optionalHttpUrl(formData, "linkedin_url"),
    portfolio_url: optionalHttpUrl(formData, "portfolio_url"),
    github_url: optionalHttpUrl(formData, "github_url"),
    skills: splitList(formString(formData, "skills")),
    languages: splitList(formString(formData, "languages")),
  };

  const yoe = formString(formData, "years_of_experience");
  if (yoe) {
    const n = Number(yoe);
    if (!Number.isNaN(n)) body.years_of_experience = n;
  }

  const openRemote = formData.get("open_to_remote");
  if (openRemote === "on" || openRemote === "true") {
    body.open_to_remote = true;
  }

  const client = getApiClient();
  const { data, error } = await createSeekerApiV1SeekersPost({ client, body });
  if (error || !data) {
    return { error: "Could not create profile. Check URLs and try again." };
  }

  redirect(`/seekers/${data.id}`);
}
