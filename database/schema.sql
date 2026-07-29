-- File: database/schema.sql
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) NOT NULL UNIQUE,
    full_name VARCHAR(255) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS resume_versions (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    version_label VARCHAR(100) NOT NULL,
    raw_text TEXT NOT NULL,
    optimized_text TEXT,
    ats_score DOUBLE PRECISION,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS job_targets (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    company_name VARCHAR(255) NOT NULL,
    role_title VARCHAR(255) NOT NULL,
    job_url VARCHAR(1024),
    job_description TEXT NOT NULL,
    fit_score DOUBLE PRECISION,
    status VARCHAR(50) NOT NULL DEFAULT 'discovered',
    preferred_locations JSONB NOT NULL DEFAULT '[]'::jsonb,
    work_mode VARCHAR(100) DEFAULT 'Any',
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS candidate_preferences (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    target_role VARCHAR(255),
    experience_level VARCHAR(100),
    skills_to_highlight JSONB NOT NULL DEFAULT '[]'::jsonb,
    preferred_locations JSONB NOT NULL DEFAULT '[]'::jsonb,
    work_mode VARCHAR(100) DEFAULT 'Any',
    work_authorization VARCHAR(255),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS workflow_sessions (
    id UUID PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_version_id INTEGER REFERENCES resume_versions(id) ON DELETE SET NULL,
    job_target_id INTEGER REFERENCES job_targets(id) ON DELETE SET NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'created',
    state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS hitl_decisions (
    id SERIAL PRIMARY KEY,
    workflow_session_id UUID NOT NULL REFERENCES workflow_sessions(id) ON DELETE CASCADE,
    gate_name VARCHAR(50) NOT NULL,
    approved BOOLEAN NOT NULL,
    reviewer_email VARCHAR(255),
    notes TEXT,
    edits_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS outreach_events (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    job_target_id INTEGER REFERENCES job_targets(id) ON DELETE SET NULL,
    recipient_email VARCHAR(255) NOT NULL,
    subject TEXT NOT NULL,
    body TEXT NOT NULL,
    status VARCHAR(50) NOT NULL DEFAULT 'queued',
    provider_message_id VARCHAR(255),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS generated_documents (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resume_version_id INTEGER REFERENCES resume_versions(id) ON DELETE CASCADE,
    document_type VARCHAR(50) NOT NULL,
    file_path TEXT NOT NULL,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_resume_versions_user_id ON resume_versions(user_id);
CREATE INDEX IF NOT EXISTS idx_job_targets_user_id ON job_targets(user_id);
CREATE INDEX IF NOT EXISTS idx_candidate_preferences_user_id ON candidate_preferences(user_id);
CREATE INDEX IF NOT EXISTS idx_workflow_sessions_user_id ON workflow_sessions(user_id);
CREATE INDEX IF NOT EXISTS idx_outreach_events_user_id ON outreach_events(user_id);
