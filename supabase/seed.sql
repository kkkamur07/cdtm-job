-- Optional demo data (NOT run by `supabase db push` on Cloud).
-- To use on Supabase Cloud: open Dashboard → SQL Editor, paste, and run on a non-prod project
-- you are willing to truncate. Production data should come from the API, not this script.
-- https://supabase.com/docs/guides/database/overview

BEGIN;

TRUNCATE public.job_locations, public.jobs, public.companies CASCADE;

INSERT INTO public.companies (id, name, slug, website, description, headquarters_location, company_size_band, industry, _is_cdtm_startup)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'Demo CDTM Startup', 'demo-cdtm', 'https://www.cdtm.com/', 'Example CDTM-affiliated company for local UI.', 'Munich, DE', '1-10', 'Education', true),
    ('00000000-0000-0000-0000-000000000002', 'Campus Spark GmbH', 'campus-spark', 'https://example.com', 'Mock B2B SaaS from the CDTM ecosystem.', 'Munich, DE', '11-50', 'Software', true),
    ('00000000-0000-0000-0000-000000000003', 'Alpine Robotics', 'alpine-robotics', 'https://example.org', 'Mock robotics startup (non-CDTM label).', 'Zurich, CH', '51-200', 'Hardware', false);

INSERT INTO public.jobs (id, company_id, title, slug, description, summary, workplace_type, employment_type, experience_level, salary_min, salary_max, salary_currency, application_url, status, published_at)
VALUES
    ('10000000-0000-0000-0000-000000000001', '00000000-0000-0000-0000-000000000001', 'Full-stack Engineer', 'fullstack-engineer', 'Build the job board and internal tools with Next.js and FastAPI.', 'Ship features end-to-end.', 'hybrid', 'full_time', 'mid', 70000, 90000, 'EUR', 'https://example.com/apply/1', 'published', now()),
    ('10000000-0000-0000-0000-000000000002', '00000000-0000-0000-0000-000000000001', 'Product Design Intern', 'product-design-intern', 'Support UX research and design systems.', '3–6 month internship.', 'onsite', 'internship', 'internship', NULL, NULL, 'EUR', NULL, 'published', now()),
    ('10000000-0000-0000-0000-000000000003', '00000000-0000-0000-0000-000000000002', 'Senior Backend Engineer', 'senior-backend', 'Design APIs and data models at scale.', 'Python / Postgres focus.', 'remote', 'full_time', 'senior', 95000, 115000, 'EUR', 'https://example.com/apply/3', 'published', now()),
    ('10000000-0000-0000-0000-000000000004', '00000000-0000-0000-0000-000000000003', 'Robotics Perception Lead', 'robotics-perception-lead', 'Lead vision and SLAM for outdoor robots.', 'Team lead role.', 'hybrid', 'full_time', 'lead', NULL, NULL, 'EUR', 'https://example.org/jobs/4', 'published', now()),
    ('10000000-0000-0000-0000-000000000005', '00000000-0000-0000-0000-000000000002', 'Draft Role — Internal Only', 'draft-internal', 'Not visible to anon readers while draft.', 'Hidden from public listings.', 'hybrid', 'full_time', 'mid', NULL, NULL, 'EUR', NULL, 'draft', NULL);

INSERT INTO public.job_locations (job_id, label, is_primary, country_code, city, sort_order)
VALUES
    ('10000000-0000-0000-0000-000000000001', 'Munich, Germany', true, 'DE', 'Munich', 0),
    ('10000000-0000-0000-0000-000000000001', 'Remote (EU)', false, NULL, NULL, 1),
    ('10000000-0000-0000-0000-000000000002', 'Munich, Germany', true, 'DE', 'Munich', 0),
    ('10000000-0000-0000-0000-000000000003', 'Remote (worldwide)', true, NULL, NULL, 0),
    ('10000000-0000-0000-0000-000000000004', 'Zurich, Switzerland', true, 'CH', 'Zurich', 0),
    ('10000000-0000-0000-0000-000000000004', 'Munich, Germany (onsite days)', false, 'DE', 'Munich', 1);

COMMIT;
