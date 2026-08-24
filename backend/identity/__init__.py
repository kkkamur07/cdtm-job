"""Identity bounded context.

An **Account** is a Supabase Auth user (Google Workspace, cdtm.com) bound to at most
one community **Member** by e-mail. This context verifies Supabase JWTs, upserts the
account on first sight and exposes the ``Principal`` dependency other contexts use
for authorization.
"""
