import type { NextConfig } from "next";

const nextConfig: NextConfig = {
    // Everything is static: ingest has already written public/data/index.json,
    // the per-member profile JSON, and the avatars into public/.
    output: "export",
    images: { unoptimized: true },
    // Pin the workspace root so a lockfile in a parent directory can't make
    // Turbopack infer the wrong one.
    turbopack: { root: __dirname },
};

export default nextConfig;