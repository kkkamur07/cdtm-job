-- Companies list filters + public seeker reads (parity with API-backed UI).

begin;

create index if not exists companies_industry_idx on public.companies (industry)
  where industry is not null;

create index if not exists companies_is_cdtm_startup_idx on public.companies (is_cdtm_startup)
  where is_cdtm_startup = true;

create index if not exists companies_hq_city_idx on public.companies (hq_city)
  where hq_city is not null;

create policy "seekers_select_public"
on public.seekers
for select
to anon, authenticated
using (true);

grant select on table public.seekers to anon, authenticated;

commit;
