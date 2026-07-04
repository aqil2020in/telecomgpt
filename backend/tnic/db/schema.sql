-- XYZ TNIC PostgreSQL schema (also created via SQLAlchemy init_db)

CREATE TABLE IF NOT EXISTS cell_snapshots (
    id SERIAL PRIMARY KEY,
    cell_id VARCHAR(64) NOT NULL,
    pci INTEGER,
    timestamp TIMESTAMPTZ DEFAULT NOW(),
    kpis JSONB NOT NULL DEFAULT '{}',
    health_score DOUBLE PRECISION,
    grade VARCHAR(16)
);
CREATE INDEX IF NOT EXISTS idx_cell_snapshots_cell ON cell_snapshots(cell_id);
CREATE INDEX IF NOT EXISTS idx_cell_snapshots_ts ON cell_snapshots(timestamp);

CREATE TABLE IF NOT EXISTS pm_counter_records (
    id SERIAL PRIMARY KEY,
    cell_id VARCHAR(64) NOT NULL,
    counter_name VARCHAR(128) NOT NULL,
    counter_value DOUBLE PRECISION NOT NULL,
    period_start TIMESTAMPTZ,
    period_end TIMESTAMPTZ,
    vendor VARCHAR(32) DEFAULT 'generic',
    meta JSONB DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_pm_cell ON pm_counter_records(cell_id);
CREATE INDEX IF NOT EXISTS idx_pm_counter ON pm_counter_records(counter_name);

CREATE TABLE IF NOT EXISTS incident_records (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(64) UNIQUE NOT NULL,
    complaint_text TEXT,
    issue_type VARCHAR(64),
    root_cause TEXT,
    resolution TEXT,
    kpis JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rca_reports (
    id SERIAL PRIMARY KEY,
    query TEXT NOT NULL,
    issue_type VARCHAR(64),
    report_json JSONB NOT NULL,
    narrative TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
