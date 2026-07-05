-- Dev seed data for local `supabase db reset` or Supabase Dashboard SQL Editor (non-prod).
-- Idempotent: fixed UUIDs + ON CONFLICT DO NOTHING.
-- Matches ``scripts/dev_seed_payloads.py``.

begin;

insert into public.companies (
  id, name, slug, legal_name, logo_url, website_url, short_description,
  industry, company_size_band, is_cdtm_startup, hq_city, hq_region, hq_country
) values
  (
    'a0000000-0000-4000-8000-000000000001'::uuid,
    'CDTM Venture Labs', 'cdtm-venture-labs', 'CDTM Venture Labs GmbH',
    'http://localhost:3000/brand/cdtm-mark.svg',
    'https://cdtm.com',
    'Entrepreneurship and innovation at the Center for Digital Technology and Management.',
    'education', 'smb', true, 'Munich', 'Bavaria', 'DE'
  ),
  (
    'a0000000-0000-4000-8000-000000000002'::uuid,
    'Alpine Robotics', 'alpine-robotics', null,
    'http://localhost:3000/brand/dev/alpine-robotics.svg',
    'https://example.com/alpine',
    'Industrial robotics and automation for SMEs.',
    'industrial', 'startup', false, 'Munich', 'Bavaria', 'DE'
  ),
  (
    'a0000000-0000-4000-8000-000000000003'::uuid,
    'North Loop Analytics', 'north-loop-analytics', 'North Loop Analytics AG',
    'http://localhost:3000/brand/dev/north-loop-analytics.svg',
    'https://example.com/northloop',
    'Product analytics and experimentation for growth teams.',
    'technology', 'mid', false, 'Berlin', 'Berlin', 'DE'
  ),
  (
    'a0000000-0000-4000-8000-000000000004'::uuid,
    'StayScout', 'stayscout', null,
    'http://localhost:3000/brand/dev/stayscout.svg',
    'https://example.com/stayscout',
    'Vacation rental search and marketplace technology.',
    'travel', 'mid', true, 'Munich', 'Bavaria', 'DE'
  ),
  (
    'a0000000-0000-4000-8000-000000000005'::uuid,
    'Flow Metrics', 'flow-metrics', null,
    'http://localhost:3000/brand/dev/flow-metrics.svg',
    'https://example.com/flowmetrics',
    'Process intelligence and enterprise automation.',
    'technology', 'enterprise', false, 'Munich', 'Bavaria', 'DE'
  ),
  (
    'a0000000-0000-4000-8000-000000000006'::uuid,
    'Orbital Works', 'orbital-works', null,
    'http://localhost:3000/brand/dev/orbital-works.svg',
    'https://example.com/orbital',
    'Launch vehicles and satellite manufacturing.',
    'aerospace', 'startup', true, 'Munich', 'Bavaria', 'DE'
  )
on conflict (id) do nothing;

insert into public.jobs (
  id, company_id, slug, title, summary, description,
  employment_type, work_arrangement, location_display, city, country,
  experience_level, must_have_skills, nice_to_have_skills, languages,
  application_email, application_url, status, visa_sponsorship, published_at
) values
  (
    'b0000000-0000-4000-8000-000000000001'::uuid,
    'a0000000-0000-4000-8000-000000000001'::uuid,
    'full-stack-engineer-cdtm', 'Full Stack Engineer (job board)',
    'Ship features for jobs.cdtm.com with FastAPI and Next.js.',
    'You will design and implement APIs, collaborate on domain models, and help ship a public job board used by CDTM students and partners.',
    'working_student', 'hybrid', 'Munich · hybrid', 'Munich', 'DE',
    'entry', array['python', 'sql', 'git'], array['fastapi', 'typescript'], array['english'],
    'careers@example.com', null, 'published', false, now() - interval '10 days'
  ),
  (
    'b0000000-0000-4000-8000-000000000002'::uuid,
    'a0000000-0000-4000-8000-000000000002'::uuid,
    'robotics-software-engineer', 'Robotics Software Engineer',
    'C++ and ROS2 for next-gen assembly cells.',
    'Join our core team building motion planning and safety-critical software for industrial robots.',
    'full_time', 'onsite', 'Munich · onsite', 'Munich', 'DE',
    'mid', array['c++', 'ros2', 'linux'], array['python', 'simulation'], array['english', 'german'],
    'jobs@example.com', 'https://example.com/alpine/apply/robotics', 'published', true, now() - interval '3 days'
  ),
  (
    'b0000000-0000-4000-8000-000000000003'::uuid,
    'a0000000-0000-4000-8000-000000000003'::uuid,
    'product-analyst-intern', 'Product Analyst Intern',
    'Summer internship: metrics, experiments, and dashboards.',
    'Support product managers with SQL analyses, cohort reporting, and experiment readouts.',
    'internship', 'remote', 'Germany · remote', 'Berlin', 'DE',
    'intern', array['sql', 'spreadsheets'], array['python', 'statistics'], array['english'],
    'interns@example.com', null, 'published', false, now() - interval '1 day'
  ),
  (
    'b0000000-0000-4000-8000-000000000004'::uuid,
    'a0000000-0000-4000-8000-000000000001'::uuid,
    'devrel-lead-draft', 'Developer Relations Lead',
    'Draft listing: community, content, and workshops.',
    'Not visible until published. You would own meetups, documentation, and partner integrations.',
    'full_time', 'hybrid', 'Munich', 'Munich', 'DE',
    'lead', array['public speaking', 'developer tools'], array['video'], array['english', 'german'],
    null, null, 'draft', null, null
  ),
  (
    'b0000000-0000-4000-8000-000000000005'::uuid,
    'a0000000-0000-4000-8000-000000000004'::uuid,
    'senior-product-manager', 'Senior Product Manager',
    'Lead zero-to-one product initiatives for our search platform.',
    'Own roadmap, discovery, and delivery for traveller-facing search experiences in Munich.',
    'full_time', 'hybrid', 'Munich, Germany', 'Munich', 'DE',
    'senior', array['product strategy', 'analytics'], '{}', array['english', 'german'],
    'careers@example.com', 'https://example.com/stayscout/careers/pm', 'published', false, now() - interval '2 days'
  ),
  (
    'b0000000-0000-4000-8000-000000000006'::uuid,
    'a0000000-0000-4000-8000-000000000005'::uuid,
    'working-student-growth', 'Working Student, Growth',
    'Support demand generation and partner marketing.',
    'Ideal for CDTM students with analytics and storytelling skills.',
    'working_student', 'remote', 'Remote (EU)', null, 'DE',
    'entry', array['marketing', 'sql'], '{}', array['english'],
    'growth@example.com', null, 'published', false, now() - interval '4 days'
  ),
  (
    'b0000000-0000-4000-8000-000000000007'::uuid,
    'a0000000-0000-4000-8000-000000000004'::uuid,
    'platform-engineer', 'Software Engineer, Platform',
    'Build scalable services on AWS for vacation rental search.',
    'TypeScript, Kotlin, and strong ownership culture.',
    'full_time', 'onsite', 'Munich, Germany', 'Munich', 'DE',
    'mid', array['typescript', 'aws', 'kubernetes'], '{}', array['english'],
    null, 'https://example.com/stayscout/careers/platform', 'published', false, now() - interval '6 days'
  ),
  (
    'b0000000-0000-4000-8000-000000000008'::uuid,
    'a0000000-0000-4000-8000-000000000006'::uuid,
    'head-of-business-development', 'Head of Business Development',
    'Lead partnerships and commercial strategy for launch services.',
    'Drive enterprise and government partnerships.',
    'full_time', 'onsite', 'Munich, Germany', 'Munich', 'DE',
    'lead', '{}', '{}', array['english', 'german'],
    'bd@example.com', null, 'published', false, now() - interval '8 days'
  ),
  (
    'b0000000-0000-4000-8000-000000000009'::uuid,
    'a0000000-0000-4000-8000-000000000005'::uuid,
    'climate-tech-internship', 'Climate Reporting Internship',
    '6-month internship on sustainability reporting tooling.',
    'Cross-functional team with mentorship from CDTM alumni.',
    'internship', 'hybrid', 'Munich, Germany', 'Munich', 'DE',
    'intern', '{}', '{}', array['english'],
    'interns@example.com', null, 'published', false, now() - interval '5 days'
  )
on conflict (id) do nothing;

insert into public.seekers (
  id, full_name, email, headline, bio,
  linkedin_url, github_url, portfolio_url,
  open_to_remote, preferred_work_arrangement,
  preferred_locations, desired_role_titles, skills, languages,
  years_of_experience, education_summary, available_from
) values
  (
    'c0000000-0000-4000-8000-000000000001'::uuid,
    'Anna Berger', 'anna.berger@example.com',
    'Product · Climate tech · CDTM Class 2025',
    'Former consultant turned PM. Built carbon accounting features used by 200+ enterprises. Led discovery with sustainability leads at mid-market manufacturers and shipped reporting workflows end-to-end.',
    'https://www.linkedin.com/in/example-anna-berger', null, 'https://example.com/anna',
    true, 'hybrid', array['Munich', 'Berlin', 'Remote EU'],
    array['product manager', 'product lead', 'climate product manager'],
    array['product strategy', 'sql', 'figma', 'climate', 'user research', 'roadmapping'],
    array['german', 'english', 'french'], 3,
    E'2024–2025 · CDTM, Technology Management\n2022–2025 · TUM, M.Sc. Management & Technology', '2026-09-01'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000002'::uuid,
    'Max Hoffmann', 'max.hoffmann@example.com',
    'Full-stack engineer · AI infrastructure',
    'Built LLM eval pipelines and inference gateways at a Series B startup. Strong in Python, TypeScript, and Kubernetes.',
    'https://www.linkedin.com/in/example-max-hoffmann', 'https://github.com/example-max', 'https://example.com/max',
    true, 'remote', array['Munich', 'Berlin', 'Remote EU'],
    array['software engineer', 'tech lead', 'staff engineer'],
    array['python', 'typescript', 'kubernetes', 'llms', 'fastapi', 'postgresql', 'aws'],
    array['english', 'german'], 5,
    E'2019–2021 · CDTM, Technology Management\n2017–2021 · TU Munich, M.Sc. Informatics', '2026-07-15'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000003'::uuid,
    'Alex Müller', 'alex.mueller@example.com',
    'M.Sc. Informatics · Backend & distributed systems',
    'CDTM alumnus with backend experience at a fintech scale-up. Designed event-driven services and observability standards.',
    'https://www.linkedin.com/in/example-alex-mueller', 'https://github.com/example-alex', null,
    true, 'hybrid', array['Munich', 'Berlin'],
    array['backend engineer', 'platform engineer', 'software engineer'],
    array['python', 'go', 'postgresql', 'kubernetes', 'kafka', 'grpc'],
    array['german', 'english'], 3,
    E'2020–2022 · CDTM, Technology Management\n2018–2022 · LMU Munich, M.Sc. Informatics', '2026-08-01'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000004'::uuid,
    'Jordan Kim', 'jordan.kim@example.com',
    'Product-focused CS student · Analytics',
    'Third-year Informatics student at TUM with CDTM elective. Built cohort dashboards and ran SQL analyses for growth experiments.',
    null, 'https://github.com/example-jordan', 'https://example.com/jordan',
    false, 'onsite', array['Munich'],
    array['product analyst', 'data analyst', 'working student product'],
    array['sql', 'python', 'notion', 'tableau', 'statistics'],
    array['english', 'korean', 'german'], 1,
    E'2025–2026 · CDTM, Elective\n2023–Present · TUM, B.Sc. Informatics', '2026-10-01'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000005'::uuid,
    'Sophie Klein', 'sophie.klein@example.com',
    'Strategy & ops · Marketplace growth',
    'Ex-BCG, scaled supply ops at a mobility marketplace from 40 to 200+ cities. Interested in chief of staff and growth strategy roles.',
    'https://www.linkedin.com/in/example-sophie-klein', null, null,
    true, 'hybrid', array['Munich', 'Berlin'],
    array['chief of staff', 'strategy manager', 'head of operations'],
    array['strategy', 'ops', 'excel', 'marketplace', 'stakeholder management', 'financial modeling'],
    array['german', 'english'], 4,
    E'2019–2021 · CDTM, Technology Management\n2017–2021 · LMU Munich, M.Sc. Management', '2026-09-15'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000006'::uuid,
    'Lena Fischer', 'lena.fischer@example.com',
    'Product designer · B2B SaaS · CDTM 2024',
    'Product designer with a focus on complex workflows and design systems. Shipped onboarding and admin consoles for HR tech.',
    'https://www.linkedin.com/in/example-lena-fischer', null, 'https://example.com/lena-design',
    true, 'hybrid', array['Munich', 'Berlin'],
    array['product designer', 'senior product designer', 'design lead'],
    array['figma', 'design systems', 'user research', 'prototyping', 'accessibility'],
    array['german', 'english'], 4,
    E'2023–2024 · CDTM, Technology Management\n2016–2021 · HfG Schwäbisch Gmünd, Interaction Design', '2026-07-01'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000007'::uuid,
    'Tomás Rivera', 'tomas.rivera@example.com',
    'Data scientist · Forecasting & experimentation',
    'Data scientist with experience in demand forecasting and pricing experiments at a travel marketplace.',
    'https://www.linkedin.com/in/example-tomas-rivera', 'https://github.com/example-tomas', null,
    true, 'remote', array['Remote EU', 'Barcelona', 'Berlin'],
    array['data scientist', 'analytics engineer', 'ml engineer'],
    array['python', 'sql', 'statistics', 'dbt', 'experimentation', 'forecasting'],
    array['english', 'spanish', 'german'], 6,
    E'2024 · CDTM, Visiting Term\n2020–2022 · UPC Barcelona, M.Sc. Data Science', '2026-06-01'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000008'::uuid,
    'Priya Sharma', 'priya.sharma@example.com',
    'Robotics M.Sc. · Controls & perception',
    'Robotics master''s student with thesis work on visual SLAM for mobile manipulators.',
    'https://www.linkedin.com/in/example-priya-sharma', 'https://github.com/example-priya', null,
    false, 'onsite', array['Munich', 'Stuttgart'],
    array['robotics intern', 'software engineer intern', 'working student robotics'],
    array['ros2', 'c++', 'python', 'computer vision', 'linux'],
    array['english', 'hindi', 'german'], 2,
    E'2024–Present · TUM, M.Sc. Robotics\n2020–2024 · IIT Delhi, B.Tech. Mechanical Engineering', '2026-09-01'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000009'::uuid,
    'Felix Wagner', 'felix.wagner@example.com',
    'Growth marketing · B2B demand gen',
    'Marketing generalist with hands-on demand gen at a climate SaaS startup. Ran LinkedIn campaigns and partner webinars.',
    'https://www.linkedin.com/in/example-felix-wagner', null, null,
    true, 'hybrid', array['Munich', 'Remote Germany'],
    array['working student marketing', 'growth marketing', 'marketing intern'],
    array['hubspot', 'linkedin ads', 'copywriting', 'analytics', 'events'],
    array['german', 'english'], 2,
    E'2025–2026 · CDTM, Elective\n2022–Present · LMU Munich, B.Sc. Business', '2026-08-15'::date
  ),
  (
    'c0000000-0000-4000-8000-000000000010'::uuid,
    'Marco Chen', 'marco.chen@example.com',
    'ML engineer · NLP & retrieval',
    'ML engineer who shipped RAG-based support tooling and document search for a legal tech startup.',
    'https://www.linkedin.com/in/example-marco-chen', 'https://github.com/example-marco', 'https://example.com/marco',
    true, 'hybrid', array['Munich', 'Berlin', 'Remote EU'],
    array['ml engineer', 'applied scientist', 'software engineer ml'],
    array['python', 'pytorch', 'llms', 'rag', 'vector search', 'mlops'],
    array['english', 'mandarin', 'german'], 4,
    E'2023–2025 · CDTM, Technology Management\n2021–2025 · ETH Zurich, M.Sc. Computer Science', '2026-07-01'::date
  )
on conflict (id) do nothing;

commit;
