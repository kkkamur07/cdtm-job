import { createClient } from "@/lib/api/generated/client";
import type { Client } from "@/lib/api/generated/client";

export function getApiClient(): Client {
  const baseUrl =
    process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
  return createClient({ baseUrl });
}
