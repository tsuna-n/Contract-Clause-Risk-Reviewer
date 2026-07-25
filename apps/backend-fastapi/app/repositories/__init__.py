"""Data access layer — one module per stored thing.

``contract`` and ``report`` are session-scoped and live in Redis with a TTL;
``audit`` is permanent and lives in Postgres.
"""
