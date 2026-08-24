/**
 * Supabase connection details, resolved in one place.
 *
 * Only the URL and the publishable (formerly anon) key are ever read here.
 * Both are `NEXT_PUBLIC_`, so both are shipped to the browser on purpose. The
 * service-role key must never appear anywhere in this app.
 *
 * Resolution is lazy and tolerant of missing values so `next build` works on a
 * machine with no env file: pages that need auth render a configuration notice
 * at runtime instead of the build failing at import time.
 */

export const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";

/**
 * Supabase renamed the browser-safe key from "anon" to "publishable". Projects
 * created before the rename still hand out the anon key, so both names are
 * accepted and the newer one wins.
 */
export const SUPABASE_PUBLISHABLE_KEY =
    process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY ??
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ??
    "";

export const isSupabaseConfigured = Boolean(SUPABASE_URL && SUPABASE_PUBLISHABLE_KEY);

/** Buckets this app uploads to. Created in the Supabase dashboard; see README. */
export const STORAGE_BUCKETS = {
    jobImages: "job-images",
    housingPhotos: "housing-photos",
} as const;
