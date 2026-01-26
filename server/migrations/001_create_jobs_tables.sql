-- Migration: Create jobs and job_history tables
-- Description: Core tables for job queue management with idempotency and audit trail
-- Version: 001
-- Date: 2026-01-24

-- Enable UUID extension if not already enabled
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Job status enum
CREATE TYPE job_status AS ENUM (
    'QUEUED',
    'RUNNING',
    'COMPLETED',
    'COMPLETED_PARTIAL',
    'FAILED',
    'FAILED_PRECHECK',
    'INTERRUPTED'
);

-- Main jobs table
CREATE TABLE IF NOT EXISTS jobs (
    job_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id VARCHAR(255) NOT NULL,
    payload_hash VARCHAR(64) NOT NULL, -- SHA256 hex
    payload_pointer TEXT NOT NULL, -- R2 path or local path
    status job_status NOT NULL DEFAULT 'QUEUED',
    
    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE,
    
    -- Worker and execution metadata
    worker_id VARCHAR(255),
    schema_version VARCHAR(50) NOT NULL DEFAULT '1.0',
    solver_version VARCHAR(50) NOT NULL DEFAULT '1.0',
    time_limit_sec INTEGER NOT NULL DEFAULT 25,
    requested_by VARCHAR(255), -- User ID or system identifier
    
    -- Results and diagnostics
    r2_url TEXT, -- Cloudflare R2 URL for result
    solve_metrics JSONB, -- {solve_time_sec, nodes, objective, soft_violations, etc}
    diagnostics JSONB, -- {summary, violations[], recommendations[]}
    
    -- Additional metadata
    progress FLOAT DEFAULT 0.0, -- 0.0 to 1.0
    error_message TEXT,
    
    -- Indexes will be created below
    CONSTRAINT check_progress CHECK (progress >= 0.0 AND progress <= 1.0)
);

-- Job history table for audit trail
CREATE TABLE IF NOT EXISTS job_history (
    id SERIAL PRIMARY KEY,
    job_id UUID NOT NULL REFERENCES jobs(job_id) ON DELETE CASCADE,
    status job_status NOT NULL,
    changed_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    changed_by VARCHAR(255), -- worker_id or system
    details JSONB, -- Additional context about the state change
    
    -- Index on job_id for efficient lookups
    CONSTRAINT fk_job_history_job FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);

-- Indexes for performance
CREATE INDEX idx_jobs_tenant ON jobs(tenant_id);
CREATE INDEX idx_jobs_payload_hash ON jobs(payload_hash);
CREATE INDEX idx_jobs_status ON jobs(status);
CREATE INDEX idx_jobs_created_at ON jobs(created_at DESC);
CREATE INDEX idx_jobs_tenant_status ON jobs(tenant_id, status);
CREATE INDEX idx_jobs_tenant_payload_hash ON jobs(tenant_id, payload_hash);

CREATE INDEX idx_job_history_job_id ON job_history(job_id, changed_at DESC);
CREATE INDEX idx_job_history_changed_at ON job_history(changed_at DESC);

-- Function to automatically insert into job_history on status change
CREATE OR REPLACE FUNCTION track_job_status_change()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'INSERT') OR (OLD.status IS DISTINCT FROM NEW.status) THEN
        INSERT INTO job_history (job_id, status, changed_by, details)
        VALUES (
            NEW.job_id,
            NEW.status,
            NEW.worker_id,
            jsonb_build_object(
                'operation', TG_OP,
                'old_status', OLD.status,
                'new_status', NEW.status,
                'progress', NEW.progress,
                'error', NEW.error_message
            )
        );
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger to track status changes
CREATE TRIGGER trigger_track_job_status_change
AFTER INSERT OR UPDATE OF status ON jobs
FOR EACH ROW
EXECUTE FUNCTION track_job_status_change();

-- View for active jobs with enriched information
CREATE OR REPLACE VIEW active_jobs AS
SELECT 
    j.job_id,
    j.tenant_id,
    j.status,
    j.created_at,
    j.started_at,
    j.worker_id,
    j.progress,
    EXTRACT(EPOCH FROM (NOW() - j.created_at)) AS age_seconds,
    CASE 
        WHEN j.started_at IS NOT NULL THEN EXTRACT(EPOCH FROM (NOW() - j.started_at))
        ELSE NULL
    END AS running_seconds
FROM jobs j
WHERE j.status IN ('QUEUED', 'RUNNING')
ORDER BY j.created_at ASC;

-- View for job metrics
CREATE OR REPLACE VIEW job_metrics AS
SELECT
    COUNT(*) FILTER (WHERE status = 'QUEUED') AS queued_count,
    COUNT(*) FILTER (WHERE status = 'RUNNING') AS running_count,
    COUNT(*) FILTER (WHERE status = 'COMPLETED') AS completed_count,
    COUNT(*) FILTER (WHERE status = 'COMPLETED_PARTIAL') AS partial_count,
    COUNT(*) FILTER (WHERE status = 'FAILED') AS failed_count,
    COUNT(*) FILTER (WHERE status = 'FAILED_PRECHECK') AS precheck_failed_count,
    COUNT(*) FILTER (WHERE status = 'INTERRUPTED') AS interrupted_count,
    AVG((solve_metrics->>'solve_time_sec')::FLOAT) FILTER (WHERE status IN ('COMPLETED', 'COMPLETED_PARTIAL')) AS avg_solve_time_sec,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY (solve_metrics->>'solve_time_sec')::FLOAT) FILTER (WHERE status IN ('COMPLETED', 'COMPLETED_PARTIAL')) AS p95_solve_time_sec
FROM jobs
WHERE created_at > NOW() - INTERVAL '24 hours';

-- Grant permissions (adjust based on your Supabase setup)
-- GRANT ALL ON jobs TO authenticated;
-- GRANT ALL ON job_history TO authenticated;
-- GRANT SELECT ON active_jobs TO authenticated;
-- GRANT SELECT ON job_metrics TO authenticated;

COMMENT ON TABLE jobs IS 'Primary job queue table with idempotency support via payload_hash';
COMMENT ON TABLE job_history IS 'Audit trail for all job status transitions';
COMMENT ON COLUMN jobs.payload_hash IS 'SHA256 of sorted JSON payload + constraints for idempotency';
COMMENT ON COLUMN jobs.payload_pointer IS 'R2 path (r2://bucket/key) or local path (file:///path)';
COMMENT ON COLUMN jobs.solve_metrics IS 'JSON with solve_time_sec, nodes, objective, soft_violations, variables_count, constraints_count';
COMMENT ON COLUMN jobs.diagnostics IS 'JSON with summary, violations array, recommendations array';
