-- Core tables: companies, jobs, seekers. RLS: anon can read companies + published jobs only.

begin;

create extension if not exists "pgcrypto";

create or replace function public.set_updated_at()
returns trigger
language plpgsql
security invoker
set search_path = ''
as $$
begin
  new.updated_at = pg_catalog.now();
  return new;
end;
$$;

create table public.companies (
  id uuid primary key default gen_random_uuid(),
  name text not null check (length(trim(name)) > 0),
  -- UNIQUE creates a btree index on slug; separate CREATE INDEX would duplicate it.
  slug text not null unique check (length(trim(slug)) > 0),
  legal_name text,

  logo_url text,
  website_url text,
  careers_page_url text,

  short_description text,
  full_description text,

  industry text,
  company_size_band text check (
    company_size_band is null
    or company_size_band in ('startup', 'smb', 'mid', 'enterprise')
  ),
  is_cdtm_startup boolean not null default false,

  hq_city text,
  hq_region text,
  hq_country text,

  linkedin_url text,
  twitter_url text,

  created_at timestamptz not null default pg_catalog.now(),
  updated_at timestamptz not null default pg_catalog.now()
);

create trigger companies_set_updated_at
before update on public.companies
for each row execute function public.set_updated_at();

create table public.jobs (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references public.companies (id) on delete cascade,
  slug text unique,  -- UNIQUE index when slug present; multiple NULLs allowed

  title text not null check (length(trim(title)) > 0),
  summary text,
  description text not null check (length(trim(description)) > 0),

  employment_type text not null check (
    employment_type in (
      'full_time',
      'part_time',
      'contract',
      'internship',
      'temporary',
      'working_student',
      'freelance'
    )
  ),
  work_arrangement text not null check (
    work_arrangement in ('onsite', 'remote', 'hybrid')
  ),

  location_display text,
  city text,
  region text,
  country text,
  remote_eligibility_note text,

  salary_min numeric(18, 2),
  salary_max numeric(18, 2),
  salary_currency char(3) check (
    salary_currency is null or salary_currency ~ '^[A-Za-z]{3}$'
  ),
  salary_period text check (
    salary_period is null or salary_period in ('yearly', 'monthly', 'hourly')
  ),
  compensation_disclosure text not null default 'undisclosed' check (
    compensation_disclosure in ('public', 'confidential', 'undisclosed')
  ),

  experience_level text not null check (
    experience_level in ('intern', 'entry', 'mid', 'senior', 'lead')
  ),
  education_level text,
  must_have_skills text[] not null default '{}',
  nice_to_have_skills text[] not null default '{}',
  languages text[] not null default '{}',

  application_url text,
  application_email text,
  valid_through date,
  status text not null default 'draft' check (
    status in ('draft', 'published', 'closed', 'filled')
  ),
  visa_sponsorship boolean,
  relocation_assistance boolean,

  created_at timestamptz not null default pg_catalog.now(),
  updated_at timestamptz not null default pg_catalog.now(),
  published_at timestamptz,

  constraint jobs_salary_range_ok check (
    salary_min is null
    or salary_max is null
    or salary_min <= salary_max
  )
);

create trigger jobs_set_updated_at
before update on public.jobs
for each row execute function public.set_updated_at();

create index jobs_company_id_idx on public.jobs (company_id);
create index jobs_published_list_idx on public.jobs (published_at desc)
  where status = 'published';

create table public.seekers (
  id uuid primary key default gen_random_uuid(),
  full_name text not null check (length(trim(full_name)) > 0),

  email text,
  phone text,
  linkedin_url text,
  portfolio_url text,
  github_url text,

  headline text,
  bio text,
  resume_url text,

  open_to_remote boolean,
  preferred_work_arrangement text check (
    preferred_work_arrangement is null
    or preferred_work_arrangement in ('onsite', 'remote', 'hybrid')
  ),
  preferred_locations text[] not null default '{}',
  desired_role_titles text[] not null default '{}',

  skills text[] not null default '{}',
  languages text[] not null default '{}',
  years_of_experience integer check (
    years_of_experience is null
    or (years_of_experience >= 0 and years_of_experience <= 80)
  ),
  education_summary text,
  available_from date,

  created_at timestamptz not null default pg_catalog.now(),
  updated_at timestamptz not null default pg_catalog.now()
);

create trigger seekers_set_updated_at
before update on public.seekers
for each row execute function public.set_updated_at();

alter table public.companies enable row level security;
alter table public.jobs enable row level security;
alter table public.seekers enable row level security;

create policy "companies_select_public"
on public.companies
for select
to anon, authenticated
using (true);

create policy "jobs_select_published"
on public.jobs
for select
to anon, authenticated
using (status = 'published');

commit;
