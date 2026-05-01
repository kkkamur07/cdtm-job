import Link from "next/link";

export default function SeekerNotFound() {
  return (
    <div className="space-y-4 text-center">
      <h1 className="text-2xl font-semibold text-zinc-900 dark:text-zinc-50">Profile not found</h1>
      <p className="text-zinc-600 dark:text-zinc-400">
        This seeker may have been removed or the link is invalid.
      </p>
      <Link
        href="/seekers"
        className="inline-block font-medium text-cdtm hover:underline dark:text-cdtm-bright"
      >
        Back to seekers
      </Link>
    </div>
  );
}
