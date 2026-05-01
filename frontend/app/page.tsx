import Link from "next/link";

export default function HomePage() {
  return (
    <div className="flex min-h-[calc(100dvh-12rem)] flex-col justify-center py-8">
      <div className="max-w-2xl space-y-5">
        <p className="text-sm font-medium uppercase tracking-[0.2em] text-white/90 drop-shadow">
          CDTM
        </p>
        <h1 className="text-4xl font-semibold tracking-tight text-white drop-shadow-lg sm:text-5xl md:text-6xl">
          Find the next rocketship.
        </h1>
        <p className="max-w-xl text-lg leading-relaxed text-zinc-100/95 drop-shadow-md">
          Browse roles from CDTM partners and innovators, or list yourself so teams can discover you.
        </p>
        <div className="flex flex-wrap gap-3 pt-3">
          <Link
            href="/jobs"
            className="inline-flex items-center justify-center rounded-lg bg-white px-5 py-2.5 text-sm font-semibold text-cdtm shadow-lg transition hover:bg-zinc-100"
          >
            Browse jobs
          </Link>
          <Link
            href="/seekers"
            className="inline-flex items-center justify-center rounded-lg border border-white/35 bg-white/10 px-5 py-2.5 text-sm font-semibold text-white shadow-lg backdrop-blur-sm transition hover:bg-white/20"
          >
            Seeker directory
          </Link>
          <Link
            href="/post-job"
            className="inline-flex items-center justify-center rounded-lg px-5 py-2.5 text-sm font-semibold text-white underline-offset-4 drop-shadow hover:underline"
          >
            Post a job
          </Link>
        </div>
      </div>
    </div>
  );
}
