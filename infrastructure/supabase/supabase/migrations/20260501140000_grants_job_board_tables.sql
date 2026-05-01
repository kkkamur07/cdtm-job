-- Explicit privileges for PostgREST JWT roles. Fixes "permission denied for table ..." when
-- the service_role key is correct but grants were not inherited as expected.

begin;

grant usage on schema public to service_role;

grant all privileges on table public.companies to service_role;
grant all privileges on table public.jobs to service_role;
grant all privileges on table public.seekers to service_role;

commit;
