import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { CompanyAvatar } from "@/components/ui/company-avatar";
import type { CompanyBoardItem } from "@/lib/format-company";

type CompanyCardProps = {
  company: CompanyBoardItem;
};

export function CompanyCard({ company }: CompanyCardProps) {
  const roleCount = company.openRoles.length;

  return (
    <Link
      href={`/companies/${company.slug}`}
      className="group flex h-full flex-col rounded-xl border border-zinc-200 bg-white p-5 shadow-sm transition-all hover:border-cdtm/30 hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-cdtm focus-visible:ring-offset-2"
    >
      <div className="flex items-start gap-4">
        <CompanyAvatar
          name={company.name}
          logoUrl={company.logo_url}
          className="h-12 w-12 shrink-0 text-sm"
        />
        <div className="min-w-0 flex-1">
          <h2 className="font-display text-lg font-medium leading-snug tracking-tight text-zinc-900 transition-colors group-hover:text-cdtm">
            {company.name}
          </h2>
        </div>
      </div>

      <p className="mt-3 line-clamp-2 min-h-[2.875rem] text-sm leading-[1.65] text-zinc-600">
        {company.short_description ?? "No description yet."}
      </p>

      <div className="mt-3 flex min-h-[4.25rem] flex-col justify-start gap-2">
        <div className="flex flex-wrap gap-1.5">
          {company.industry && <Badge variant="muted">{company.industry}</Badge>}
          <Badge variant="muted">{company.hqLabel}</Badge>
        </div>
        <div className="flex min-h-[1.625rem] flex-wrap items-start gap-1.5">
          {company.is_cdtm_startup && <Badge variant="accent">CDTM startup</Badge>}
        </div>
      </div>

      <p className="mt-auto border-t border-zinc-100 pt-3 text-sm font-medium text-zinc-500">
        {roleCount} open {roleCount === 1 ? "role" : "roles"}
      </p>
    </Link>
  );
}
