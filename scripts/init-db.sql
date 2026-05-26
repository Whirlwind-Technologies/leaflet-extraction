-- =============================================================================
-- AI-Powered Leaflet Data Extraction Platform
-- Database Initialization Script
-- =============================================================================
-- This script is run when the PostgreSQL container is first initialized.
-- It creates necessary extensions and initial configuration.
-- =============================================================================

-- Enable required extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";  -- For text search

-- Create indexes for better performance (if tables exist)
-- These will be handled by Alembic migrations, but this ensures
-- the extensions are available.

-- Log initialization
DO $$
BEGIN
    RAISE NOTICE 'Database initialized successfully';
END
$$;