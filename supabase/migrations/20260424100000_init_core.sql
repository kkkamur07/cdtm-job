-- CDTM Job Board: core schema (companies, jobs, job_locations) + RLS for public read

-- Companies
CREATE TABLE public.companies (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    slug text NOT NULL UNIQUE,
    website text,
    logo_url text,
    description text,
    headquarters_location text,
    company_size_band text,
    industry text,
    _is_cdtm_startup boolean NOT NULL DEFAULT false,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

-- Jobs
CREATE TABLE public.jobs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    company_id uuid NOT NULL REFERENCES public.companies (id) ON DELETE CASCADE,
    title text NOT NULL,
    slug text NOT NULL,
    description text NOT NULL,
    summary text,
    workplace_type text,
    employment_type text,
    experience_level text,
    department text,
    salary_min numeric,
    salary_max numeric,
    salary_currency text NOT NULL DEFAULT 'EUR',
    application_url text,
    application_email text,
    visa_sponsorship boolean,
    status text NOT NULL DEFAULT 'draft' CHECK (status IN ('draft', 'published', 'closed')),
    published_at timestamptz,
    closes_at timestamptz,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT jobs_company_slug_unique UNIQUE (company_id, slug)
);

CREATE INDEX jobs_company_id_idx ON public.jobs (company_id);
CREATE INDEX jobs_status_idx ON public.jobs (status);

-- Multiple locations per job: this *is* the "list" of locations, stored relationally.
-- Each row is one location; many rows share the same job_id (one-to-many).
-- Alternative would be a single JSONB column on jobs (simpler reads, weaker querying/indexing).
CREATE TABLE public.job_locations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id uuid NOT NULL REFERENCES public.jobs (id) ON DELETE CASCADE,
    label text NOT NULL,
    is_primary boolean NOT NULL DEFAULT false,
    country_code text,
    city text,
    sort_order integer NOT NULL DEFAULT 0
);

CREATE INDEX job_locations_job_id_idx ON public.job_locations (job_id);

-- Row Level Security (RLS): per-row access rules enforced by Postgres for every query,
-- including the Supabase PostgREST API. Here, anon/authenticated users may only SELECT
-- published jobs (and related locations); writes use the service role from FastAPI.
ALTER TABLE public.companies ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.jobs ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.job_locations ENABLE ROW LEVEL SECURITY;

-- Anyone can read companies (metadata for cards); tighten later if needed
CREATE POLICY companies_select_public
    ON public.companies
    FOR SELECT
    TO anon, authenticated
    USING (true);

CREATE POLICY jobs_select_published
    ON public.jobs
    FOR SELECT
    TO anon, authenticated
    USING (status = 'published');

CREATE POLICY job_locations_select_published
    ON public.job_locations
    FOR SELECT
    TO anon, authenticated
    USING (
        EXISTS (
            SELECT 1
            FROM public.jobs j
            WHERE j.id = job_locations.job_id
              AND j.status = 'published'
        )
    );

-- Writes: only service role (bypasses RLS) or future authenticated policies
-- No INSERT/UPDATE policies for anon — FastAPI uses service_role key.
-- Optional demo data: see supabase/seed.sql (apply manually in Dashboard SQL Editor if desired; not run by db push).

-- Explicit grants for PostgREST anon role (Supabase defaults may cover this; safe for fresh projects)
GRANT USAGE ON SCHEMA public TO anon, authenticated;
GRANT SELECT ON public.companies TO anon, authenticated;
GRANT SELECT ON public.jobs TO anon, authenticated;
GRANT SELECT ON public.job_locations TO anon, authenticated;
