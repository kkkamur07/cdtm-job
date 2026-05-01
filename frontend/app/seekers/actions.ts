"use server";

import { redirect } from "next/navigation";

import { createSeekerApiV1SeekersPost } from "@/lib/api/generated";
import type { SeekerCreate } from "@/lib/api/generated";
import { getApiClient } from "@/lib/api/get-client";

export type SeekerActionState = { error?: string } | null;

function str(formData: FormData, key: string): string {
  return String(formData.get(key) ?? "").trim();
}

function optionalUrl(formData: FormData, key: string): string | null {
  const v = str(formData, key);
  return v || null;
}

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
  const full_name = str(formData, "full_name");
  if (!full_name) {
    return { error: "Name is required." };
  }

  const body: SeekerCreate = {
    full_name,
    email: str(formData, "email") || null,
    headline: str(formData, "headline") || null,
    bio: str(formData, "bio") || null,
    linkedin_url: optionalUrl(formData, "linkedin_url"),
    portfolio_url: optionalUrl(formData, "portfolio_url"),
    github_url: optionalUrl(formData, "github_url"),
    skills: splitList(str(formData, "skills")),
    languages: splitList(str(formData, "languages")),
  };

  const yoe = str(formData, "years_of_experience");
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

  redirect("/seekers");
}
