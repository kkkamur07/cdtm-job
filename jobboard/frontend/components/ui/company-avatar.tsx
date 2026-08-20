"use client";

import { useState } from "react";

import { companyLogoSrc } from "@/lib/company-logo";

type CompanyAvatarProps = {
  name: string;
  logoUrl?: string | null;
  className?: string;
};

function initials(name: string): string {
  const words = name.trim().split(/\s+/).filter(Boolean);
  if (words.length === 0) return "?";
  if (words.length === 1) return words[0].slice(0, 2).toUpperCase();
  return (words[0][0] + words[1][0]).toUpperCase();
}

export function CompanyAvatar({ name, logoUrl, className = "" }: CompanyAvatarProps) {
  const [failed, setFailed] = useState(false);
  const src = companyLogoSrc(logoUrl);
  const showLogo = src && !failed;

  return (
    <div
      className={`flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-lg bg-cdtm/10 text-xs font-bold tracking-tight text-cdtm ring-1 ring-inset ring-cdtm/15 ${className}`}
      aria-hidden={!showLogo}
    >
      {showLogo ? (
        <img
          src={src}
          alt=""
          className="h-full w-full object-contain p-1.5"
          onError={() => setFailed(true)}
        />
      ) : (
        initials(name)
      )}
    </div>
  );
}
