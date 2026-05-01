import type { Metadata } from "next";
import Link from "next/link";

import { SeekerProfileForm } from "@/components/seeker-profile-form";

export const metadata: Metadata = {
  title: "New seeker profile",
};

export default function NewSeekerPage() {
  return (
    <div className="space-y-8">
      <div>
        <Link
          href="/seekers"
          className="text-sm font-medium text-cdtm hover:underline dark:text-cdtm-bright"
        >
          ← Seekers
        </Link>
        <h1 className="mt-4 text-3xl font-semibold tracking-tight text-zinc-900 dark:text-zinc-50">
          Create your profile
        </h1>
        <p className="mt-2 text-zinc-600 dark:text-zinc-400">
          Share how you want to be found by CDTM hiring partners. Listing is public via the API;
          tighten access in production if needed.
        </p>
      </div>
      <SeekerProfileForm />
    </div>
  );
}
