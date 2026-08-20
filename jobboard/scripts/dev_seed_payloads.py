"""Static payloads for ``scripts/seed_dev_data.py`` and ``supabase/seed.sql``."""

from __future__ import annotations

from typing import Any

# Logos live in ``frontend/public/`` and are served by Next.js in local dev.
DEV_PUBLIC_ASSET_BASE = "http://localhost:3000"


def dev_logo_url(path: str) -> str:
    return f"{DEV_PUBLIC_ASSET_BASE}{path}"


# Fixed UUIDs keep SQL seed and API seed aligned.
DEV_COMPANIES: list[dict[str, Any]] = [
    {
        "slug": "cdtm-venture-labs",
        "name": "CDTM Venture Labs",
        "legal_name": "CDTM Venture Labs GmbH",
        "logo_url": dev_logo_url("/brand/cdtm-mark.svg"),
        "website_url": "https://cdtm.com",
        "short_description": "Entrepreneurship and innovation at the Center for Digital Technology and Management.",
        "industry": "education",
        "company_size_band": "smb",
        "is_cdtm_startup": True,
        "hq_city": "Munich",
        "hq_region": "Bavaria",
        "hq_country": "DE",
        "full_description": (
            "CDTM Venture Labs supports student founders and partner companies building digital "
            "products. Teams work across product, engineering, and go-to-market with mentorship "
            "from CDTM faculty and alumni."
        ),
    },
    {
        "slug": "alpine-robotics",
        "name": "Alpine Robotics",
        "logo_url": dev_logo_url("/brand/dev/alpine-robotics.svg"),
        "website_url": "https://example.com/alpine",
        "short_description": "Industrial robotics and automation for SMEs.",
        "industry": "industrial",
        "company_size_band": "startup",
        "is_cdtm_startup": False,
        "hq_city": "Munich",
        "hq_region": "Bavaria",
        "hq_country": "DE",
    },
    {
        "slug": "north-loop-analytics",
        "name": "North Loop Analytics",
        "legal_name": "North Loop Analytics AG",
        "logo_url": dev_logo_url("/brand/dev/north-loop-analytics.svg"),
        "website_url": "https://example.com/northloop",
        "short_description": "Product analytics and experimentation for growth teams.",
        "industry": "technology",
        "company_size_band": "mid",
        "is_cdtm_startup": False,
        "hq_city": "Berlin",
        "hq_region": "Berlin",
        "hq_country": "DE",
    },
    {
        "slug": "stayscout",
        "name": "StayScout",
        "logo_url": dev_logo_url("/brand/dev/stayscout.svg"),
        "website_url": "https://example.com/stayscout",
        "short_description": "Vacation rental search and marketplace technology.",
        "industry": "travel",
        "company_size_band": "mid",
        "is_cdtm_startup": True,
        "hq_city": "Munich",
        "hq_region": "Bavaria",
        "hq_country": "DE",
    },
    {
        "slug": "flow-metrics",
        "name": "Flow Metrics",
        "logo_url": dev_logo_url("/brand/dev/flow-metrics.svg"),
        "website_url": "https://example.com/flowmetrics",
        "short_description": "Process intelligence and enterprise automation.",
        "industry": "technology",
        "company_size_band": "enterprise",
        "is_cdtm_startup": False,
        "hq_city": "Munich",
        "hq_region": "Bavaria",
        "hq_country": "DE",
    },
    {
        "slug": "orbital-works",
        "name": "Orbital Works",
        "logo_url": dev_logo_url("/brand/dev/orbital-works.svg"),
        "website_url": "https://example.com/orbital",
        "short_description": "Launch vehicles and satellite manufacturing.",
        "industry": "aerospace",
        "company_size_band": "startup",
        "is_cdtm_startup": True,
        "hq_city": "Munich",
        "hq_region": "Bavaria",
        "hq_country": "DE",
    },
]

# ``company_slug`` must match a company above. ``status``: published jobs appear on the board.
DEV_JOBS: list[dict[str, Any]] = [
    {
        "company_slug": "cdtm-venture-labs",
        "slug": "full-stack-engineer-cdtm",
        "title": "Full Stack Engineer (job board)",
        "summary": "Ship features for jobs.cdtm.com with FastAPI and Next.js.",
        "description": (
            "You will design and implement APIs, collaborate on domain models, and help ship "
            "a public job board used by CDTM students and partners. Stack: Python, FastAPI, "
            "PostgreSQL, TypeScript, React."
        ),
        "employment_type": "working_student",
        "work_arrangement": "hybrid",
        "experience_level": "entry",
        "location_display": "Munich · hybrid",
        "city": "Munich",
        "country": "DE",
        "application_email": "careers@example.com",
        "status": "published",
        "must_have_skills": ["python", "sql", "git"],
        "nice_to_have_skills": ["fastapi", "typescript"],
        "languages": ["english"],
    },
    {
        "company_slug": "alpine-robotics",
        "slug": "robotics-software-engineer",
        "title": "Robotics Software Engineer",
        "summary": "C++ and ROS2 for next-gen assembly cells.",
        "description": (
            "Join our core team building motion planning and safety-critical software for "
            "industrial robots. You will work closely with hardware and field engineers."
        ),
        "employment_type": "full_time",
        "work_arrangement": "onsite",
        "experience_level": "mid",
        "location_display": "Munich · onsite",
        "city": "Munich",
        "country": "DE",
        "application_email": "jobs@example.com",
        "application_url": "https://example.com/alpine/apply/robotics",
        "status": "published",
        "must_have_skills": ["c++", "ros2", "linux"],
        "nice_to_have_skills": ["python", "simulation"],
        "languages": ["english", "german"],
        "visa_sponsorship": True,
    },
    {
        "company_slug": "north-loop-analytics",
        "slug": "product-analyst-intern",
        "title": "Product Analyst Intern",
        "summary": "Summer internship: metrics, experiments, and dashboards.",
        "description": (
            "Support product managers with SQL analyses, cohort reporting, and experiment "
            "readouts. Ideal if you enjoy turning messy data into decisions."
        ),
        "employment_type": "internship",
        "work_arrangement": "remote",
        "experience_level": "intern",
        "location_display": "Germany · remote",
        "city": "Berlin",
        "country": "DE",
        "application_email": "interns@example.com",
        "status": "published",
        "must_have_skills": ["sql", "spreadsheets"],
        "nice_to_have_skills": ["python", "statistics"],
        "languages": ["english"],
    },
    {
        "company_slug": "stayscout",
        "slug": "senior-product-manager",
        "title": "Senior Product Manager",
        "summary": "Lead zero-to-one product initiatives for our search platform.",
        "description": (
            "Own roadmap, discovery, and delivery for traveller-facing search experiences. "
            "Partner with design, engineering, and data science in Munich."
        ),
        "employment_type": "full_time",
        "work_arrangement": "hybrid",
        "experience_level": "senior",
        "location_display": "Munich, Germany",
        "city": "Munich",
        "country": "DE",
        "application_url": "https://example.com/stayscout/careers/pm",
        "application_email": "careers@example.com",
        "status": "published",
        "must_have_skills": ["product strategy", "analytics"],
        "languages": ["english", "german"],
    },
    {
        "company_slug": "flow-metrics",
        "slug": "working-student-growth",
        "title": "Working Student, Growth",
        "summary": "Support demand generation and partner marketing.",
        "description": (
            "Ideal for CDTM students with analytics and storytelling skills. Help run campaigns, "
            "build dashboards, and coordinate community events across the DACH region."
        ),
        "employment_type": "working_student",
        "work_arrangement": "remote",
        "experience_level": "entry",
        "location_display": "Remote (EU)",
        "country": "DE",
        "application_email": "growth@example.com",
        "status": "published",
        "must_have_skills": ["marketing", "sql"],
        "languages": ["english"],
    },
    {
        "company_slug": "stayscout",
        "slug": "platform-engineer",
        "title": "Software Engineer, Platform",
        "summary": "Build scalable services on AWS for vacation rental search.",
        "description": (
            "TypeScript, Kotlin, and strong ownership culture. You will design APIs, improve "
            "reliability, and mentor junior engineers."
        ),
        "employment_type": "full_time",
        "work_arrangement": "onsite",
        "experience_level": "mid",
        "location_display": "Munich, Germany",
        "city": "Munich",
        "country": "DE",
        "application_url": "https://example.com/stayscout/careers/platform",
        "status": "published",
        "must_have_skills": ["typescript", "aws", "kubernetes"],
        "languages": ["english"],
    },
    {
        "company_slug": "orbital-works",
        "slug": "head-of-business-development",
        "title": "Head of Business Development",
        "summary": "Lead partnerships and commercial strategy for launch services.",
        "description": (
            "Drive enterprise and government partnerships. Background in aerospace, consulting, "
            "or B2B sales required."
        ),
        "employment_type": "full_time",
        "work_arrangement": "onsite",
        "experience_level": "lead",
        "location_display": "Munich, Germany",
        "city": "Munich",
        "country": "DE",
        "application_email": "bd@example.com",
        "status": "published",
        "languages": ["english", "german"],
    },
    {
        "company_slug": "flow-metrics",
        "slug": "climate-tech-internship",
        "title": "Climate Reporting Internship",
        "summary": "6-month internship on sustainability reporting tooling.",
        "description": (
            "Cross-functional team with mentorship from CDTM alumni. Work on data pipelines "
            "for carbon accounting features."
        ),
        "employment_type": "internship",
        "work_arrangement": "hybrid",
        "experience_level": "intern",
        "location_display": "Munich, Germany",
        "city": "Munich",
        "country": "DE",
        "application_email": "interns@example.com",
        "status": "published",
        "languages": ["english"],
    },
    {
        "company_slug": "cdtm-venture-labs",
        "slug": "devrel-lead-draft",
        "title": "Developer Relations Lead",
        "summary": "Draft listing: community, content, and workshops.",
        "description": "Not visible until published. You would own meetups, documentation, and partner integrations.",
        "employment_type": "full_time",
        "work_arrangement": "hybrid",
        "experience_level": "lead",
        "location_display": "Munich",
        "city": "Munich",
        "country": "DE",
        "status": "draft",
        "must_have_skills": ["public speaking", "developer tools"],
        "languages": ["english", "german"],
    },
]

DEV_SEEKERS: list[dict[str, Any]] = [
    {
        "email": "anna.berger@example.com",
        "full_name": "Anna Berger",
        "headline": "Product · Climate tech · CDTM Class 2025",
        "bio": (
            "Former consultant turned PM. Built carbon accounting features used by 200+ enterprises. "
            "Led discovery with sustainability leads at mid-market manufacturers and shipped reporting "
            "workflows end-to-end. Open to Munich or remote EU roles where climate impact is core to the product."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-anna-berger",
        "portfolio_url": "https://example.com/anna",
        "open_to_remote": True,
        "preferred_work_arrangement": "hybrid",
        "preferred_locations": ["Munich", "Berlin", "Remote EU"],
        "desired_role_titles": ["product manager", "product lead", "climate product manager"],
        "skills": ["product strategy", "sql", "figma", "climate", "user research", "roadmapping"],
        "languages": ["german", "english", "french"],
        "years_of_experience": 3,
        "education_summary": (
            "2024–2025 · CDTM, Technology Management\n"
            "2022–2025 · TUM, M.Sc. Management & Technology"
        ),
        "available_from": "2026-09-01",
    },
    {
        "email": "max.hoffmann@example.com",
        "full_name": "Max Hoffmann",
        "headline": "Full-stack engineer · AI infrastructure",
        "bio": (
            "Built LLM eval pipelines and inference gateways at a Series B startup. Strong in Python, "
            "TypeScript, and Kubernetes. Comfortable owning services from API design to on-call. "
            "Looking for senior IC or tech lead roles on small, high-trust teams."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-max-hoffmann",
        "github_url": "https://github.com/example-max",
        "portfolio_url": "https://example.com/max",
        "open_to_remote": True,
        "preferred_work_arrangement": "remote",
        "preferred_locations": ["Munich", "Berlin", "Remote EU"],
        "desired_role_titles": ["software engineer", "tech lead", "staff engineer"],
        "skills": ["python", "typescript", "kubernetes", "llms", "fastapi", "postgresql", "aws"],
        "languages": ["english", "german"],
        "years_of_experience": 5,
        "education_summary": (
            "2019–2021 · CDTM, Technology Management\n"
            "2017–2021 · TU Munich, M.Sc. Informatics"
        ),
        "available_from": "2026-07-15",
    },
    {
        "email": "alex.mueller@example.com",
        "full_name": "Alex Müller",
        "headline": "M.Sc. Informatics · Backend & distributed systems",
        "bio": (
            "CDTM alumnus with backend experience at a fintech scale-up. Designed event-driven services "
            "handling payment webhooks and built observability standards for a 12-person engineering team. "
            "Interested in early-stage product teams in Munich and Berlin."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-alex-mueller",
        "github_url": "https://github.com/example-alex",
        "open_to_remote": True,
        "preferred_work_arrangement": "hybrid",
        "preferred_locations": ["Munich", "Berlin"],
        "desired_role_titles": ["backend engineer", "platform engineer", "software engineer"],
        "skills": ["python", "go", "postgresql", "kubernetes", "kafka", "grpc"],
        "languages": ["german", "english"],
        "years_of_experience": 3,
        "education_summary": (
            "2020–2022 · CDTM, Technology Management\n"
            "2018–2022 · LMU Munich, M.Sc. Informatics"
        ),
        "available_from": "2026-08-01",
    },
    {
        "email": "jordan.kim@example.com",
        "full_name": "Jordan Kim",
        "headline": "Product-focused CS student · Analytics",
        "bio": (
            "Third-year Informatics student at TUM with CDTM elective. Built cohort dashboards for a "
            "campus startup and ran SQL analyses for growth experiments. Seeking working student or "
            "internship roles in product analytics where I can learn from strong mentors."
        ),
        "github_url": "https://github.com/example-jordan",
        "portfolio_url": "https://example.com/jordan",
        "open_to_remote": False,
        "preferred_work_arrangement": "onsite",
        "preferred_locations": ["Munich"],
        "desired_role_titles": ["product analyst", "data analyst", "working student product"],
        "skills": ["sql", "python", "notion", "tableau", "statistics"],
        "languages": ["english", "korean", "german"],
        "years_of_experience": 1,
        "education_summary": (
            "2025–2026 · CDTM, Elective\n"
            "2023–Present · TUM, B.Sc. Informatics"
        ),
        "available_from": "2026-10-01",
    },
    {
        "email": "sophie.klein@example.com",
        "full_name": "Sophie Klein",
        "headline": "Strategy & ops · Marketplace growth",
        "bio": (
            "Ex-BCG, scaled supply ops at a mobility marketplace from 40 to 200+ cities. Owned rider "
            "and driver incentive design, weekly business reviews, and cross-functional launch playbooks. "
            "Interested in chief of staff and growth strategy roles in Munich or Berlin."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-sophie-klein",
        "open_to_remote": True,
        "preferred_work_arrangement": "hybrid",
        "preferred_locations": ["Munich", "Berlin"],
        "desired_role_titles": ["chief of staff", "strategy manager", "head of operations"],
        "skills": ["strategy", "ops", "excel", "marketplace", "stakeholder management", "financial modeling"],
        "languages": ["german", "english"],
        "years_of_experience": 4,
        "education_summary": (
            "2019–2021 · CDTM, Technology Management\n"
            "2017–2021 · LMU Munich, M.Sc. Management"
        ),
        "available_from": "2026-09-15",
    },
    {
        "email": "lena.fischer@example.com",
        "full_name": "Lena Fischer",
        "headline": "Product designer · B2B SaaS · CDTM 2024",
        "bio": (
            "Product designer with a focus on complex workflows and design systems. Shipped onboarding "
            "and admin consoles for HR tech used by 50k+ monthly active users. Looking for senior product "
            "design or design lead roles in Munich."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-lena-fischer",
        "portfolio_url": "https://example.com/lena-design",
        "open_to_remote": True,
        "preferred_work_arrangement": "hybrid",
        "preferred_locations": ["Munich", "Berlin"],
        "desired_role_titles": ["product designer", "senior product designer", "design lead"],
        "skills": ["figma", "design systems", "user research", "prototyping", "accessibility"],
        "languages": ["german", "english"],
        "years_of_experience": 4,
        "education_summary": (
            "2023–2024 · CDTM, Technology Management\n"
            "2016–2021 · HfG Schwäbisch Gmünd, Interaction Design"
        ),
        "available_from": "2026-07-01",
    },
    {
        "email": "tomas.rivera@example.com",
        "full_name": "Tomás Rivera",
        "headline": "Data scientist · Forecasting & experimentation",
        "bio": (
            "Data scientist with experience in demand forecasting and pricing experiments at a travel "
            "marketplace. Comfortable in Python, dbt, and Snowflake; published internal playbooks for "
            "A/B test design. Open to remote-first teams across the EU."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-tomas-rivera",
        "github_url": "https://github.com/example-tomas",
        "open_to_remote": True,
        "preferred_work_arrangement": "remote",
        "preferred_locations": ["Remote EU", "Barcelona", "Berlin"],
        "desired_role_titles": ["data scientist", "analytics engineer", "ml engineer"],
        "skills": ["python", "sql", "statistics", "dbt", "experimentation", "forecasting"],
        "languages": ["english", "spanish", "german"],
        "years_of_experience": 6,
        "education_summary": (
            "2024 · CDTM, Visiting Term\n"
            "2020–2022 · UPC Barcelona, M.Sc. Data Science"
        ),
        "available_from": "2026-06-01",
    },
    {
        "email": "priya.sharma@example.com",
        "full_name": "Priya Sharma",
        "headline": "Robotics M.Sc. · Controls & perception",
        "bio": (
            "Robotics master's student with thesis work on visual SLAM for mobile manipulators. "
            "Interned at an industrial automation startup on ROS2 integration. Looking for internship "
            "or working student roles in robotics software or perception."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-priya-sharma",
        "github_url": "https://github.com/example-priya",
        "open_to_remote": False,
        "preferred_work_arrangement": "onsite",
        "preferred_locations": ["Munich", "Stuttgart"],
        "desired_role_titles": ["robotics intern", "software engineer intern", "working student robotics"],
        "skills": ["ros2", "c++", "python", "computer vision", "linux"],
        "languages": ["english", "hindi", "german"],
        "years_of_experience": 2,
        "education_summary": (
            "2024–Present · TUM, M.Sc. Robotics\n"
            "2020–2024 · IIT Delhi, B.Tech. Mechanical Engineering"
        ),
        "available_from": "2026-09-01",
    },
    {
        "email": "felix.wagner@example.com",
        "full_name": "Felix Wagner",
        "headline": "Growth marketing · B2B demand gen",
        "bio": (
            "Marketing generalist with hands-on demand gen at a climate SaaS startup. Ran LinkedIn "
            "campaigns, partner webinars, and CRM hygiene in HubSpot. Seeking working student or junior "
            "growth roles while finishing my degree."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-felix-wagner",
        "open_to_remote": True,
        "preferred_work_arrangement": "hybrid",
        "preferred_locations": ["Munich", "Remote Germany"],
        "desired_role_titles": ["working student marketing", "growth marketing", "marketing intern"],
        "skills": ["hubspot", "linkedin ads", "copywriting", "analytics", "events"],
        "languages": ["german", "english"],
        "years_of_experience": 2,
        "education_summary": (
            "2025–2026 · CDTM, Elective\n"
            "2022–Present · LMU Munich, B.Sc. Business"
        ),
        "available_from": "2026-08-15",
    },
    {
        "email": "marco.chen@example.com",
        "full_name": "Marco Chen",
        "headline": "ML engineer · NLP & retrieval",
        "bio": (
            "ML engineer who shipped RAG-based support tooling and document search for a legal tech "
            "startup. Experience fine-tuning open models and building eval harnesses. Interested in "
            "applied ML roles with strong product engineering culture."
        ),
        "linkedin_url": "https://www.linkedin.com/in/example-marco-chen",
        "github_url": "https://github.com/example-marco",
        "portfolio_url": "https://example.com/marco",
        "open_to_remote": True,
        "preferred_work_arrangement": "hybrid",
        "preferred_locations": ["Munich", "Berlin", "Remote EU"],
        "desired_role_titles": ["ml engineer", "applied scientist", "software engineer ml"],
        "skills": ["python", "pytorch", "llms", "rag", "vector search", "mlops"],
        "languages": ["english", "mandarin", "german"],
        "years_of_experience": 4,
        "education_summary": (
            "2023–2025 · CDTM, Technology Management\n"
            "2021–2025 · ETH Zurich, M.Sc. Computer Science"
        ),
        "available_from": "2026-07-01",
    },
]
