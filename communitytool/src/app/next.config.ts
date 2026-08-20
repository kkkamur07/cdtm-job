import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Everything is static: the ingest script has already written index.json,
  // the per-member profile JSON, and the avatars into public/.
  output: "export",
  images: { unoptimized: true },
};

export default nextConfig;
