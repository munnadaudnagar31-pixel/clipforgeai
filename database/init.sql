-- ─────────────────────────────────────────────────────────────────
-- ClipForge AI — PostgreSQL Initialization Script
-- Runs once on first container start via docker-entrypoint-initdb.d/
-- ─────────────────────────────────────────────────────────────────

-- Enable UUID generation
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Enable trigram-based full-text search (for clip/video title search)
CREATE EXTENSION IF NOT EXISTS "pg_trgm";

-- Enable btree_gist (for exclusion constraints on date ranges)
CREATE EXTENSION IF NOT EXISTS "btree_gist";

-- ── Indexes created by SQLAlchemy at startup ────────────────────
-- SQLAlchemy/Alembic will create the actual tables and indexes.
-- This script only handles extensions and any raw SQL bootstrap.

-- ── Default search path ─────────────────────────────────────────
ALTER ROLE clipforge SET search_path TO public;

-- ── Helpful views (optional, created after tables exist) ─────────
-- These are safe to re-run; they use CREATE OR REPLACE.
-- They will be created by the application after tables exist.

-- Log
DO $$
BEGIN
  RAISE NOTICE 'ClipForge AI — database init complete. Extensions: uuid-ossp, pg_trgm, btree_gist.';
END $$;
