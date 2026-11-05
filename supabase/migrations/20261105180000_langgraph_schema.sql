-- Migration 7: a private schema for LangGraph's checkpointer tables (D-012).
-- LangGraph creates its own tables there (checkpoints, checkpoint_blobs, checkpoint_writes,
-- checkpoint_migrations) when backend/scripts/migrate.py runs PostgresSaver.setup().
-- Only the backend's admin connection uses it; user roles get no access at all.

create schema if not exists langgraph;

revoke all on schema langgraph from public, anon, authenticated;
