"""CDTM Community backend: one FastAPI app, several bounded contexts.

* ``core``      cross-cutting app factory, settings, errors, shared schemas
* ``identity``  accounts (Supabase Auth users bound to Members)
* ``community`` members, entries, intents, events, announcements, housing, paths
* ``jobboard``  companies, jobs, seekers (ported from the original job board)
"""
