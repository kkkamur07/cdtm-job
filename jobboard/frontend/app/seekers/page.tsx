import type { Metadata } from "next";

import { SeekersBoard } from "@/components/seekers/seekers-board";
import { fetchSeekers } from "@/lib/data/api";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Discover candidates",
};

export default async function SeekersPage() {
  const page = await fetchSeekers();
  return <SeekersBoard seekers={page.items} />;
}
