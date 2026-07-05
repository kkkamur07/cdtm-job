import Link from "next/link";

export default function SeekerNotFound() {
  return (
    <div className="space-y-4 text-center">
      <h1 className="font-display text-2xl font-medium text-zinc-900">Profile not found</h1>
      <p className="text-zinc-600">This seeker may have been removed or the link is invalid.</p>
      <Link href="/seekers" className="inline-block font-medium text-cdtm hover:underline">
        Back to seekers
      </Link>
    </div>
  );
}
