"""Job board bounded context: companies, jobs, seekers.

Ported from the original standalone job board. The public API contract under
``/api/v1/{companies,jobs,seekers}`` is unchanged; persistence moved from
supabase-py/PostgREST to SQLAlchemy against the same Postgres.
"""
