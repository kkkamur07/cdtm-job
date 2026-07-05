import type { Metadata } from "next";

import { BackLink } from "@/components/ui/back-link";
import { PageHeader } from "@/components/ui/page-header";
import { SeekerProfileForm } from "@/components/seeker-profile-form";

export const metadata: Metadata = {
  title: "New seeker profile",
};

export default function NewSeekerPage() {
  return (
    <div className="space-y-8">
      <BackLink href="/seekers">Seekers</BackLink>
      <PageHeader
        eyebrow="Directory"
        title="Create your profile"
        description="Share how you want to be found by CDTM hiring partners. Listing is public via the API; tighten access in production if needed."
      />
      <SeekerProfileForm />
    </div>
  );
}
