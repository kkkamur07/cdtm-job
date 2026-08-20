import Link from "next/link";

import { BackLink } from "@/components/ui/back-link";
import { EmptyState } from "@/components/ui/empty-state";

export default function CompanyNotFound() {
  return (
    <div className="space-y-6">
      <BackLink href="/companies">All companies</BackLink>
      <EmptyState
        title="Company not found"
        description={
          <>
            This profile is not in the sample directory.{" "}
            <Link href="/companies" className="font-medium text-cdtm hover:underline">
              Browse companies
            </Link>
            .
          </>
        }
      />
    </div>
  );
}
