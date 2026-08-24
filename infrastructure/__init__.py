"""Shared infrastructure: database engine, declarative base and Alembic migrations.

Bounded contexts (``backend/<context>/infrastructure``) own their ORM models and
repositories; this package only owns the engine/session plumbing and the migration
environment that stitches every context's tables into one schema.
"""
