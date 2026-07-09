-- US6 (spec FR-024/FR-025): self-contained shareable itinerary document.
-- download_available is CHECKed true — FR-025 requires the download path to
-- always succeed regardless of whether the hosted link upload did.

CREATE TABLE shareable_itinerary_reports (
    report_id           TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    html_ref            TEXT,
    link_url            TEXT,
    link_expires_at     TIMESTAMPTZ,
    download_available  BOOLEAN NOT NULL DEFAULT true CHECK (download_available = true),
    generated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE shareable_itinerary_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE shareable_itinerary_reports FORCE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON shareable_itinerary_reports
    USING (tenant_id = current_setting('app.tenant_id', true));

-- 0003_app_role.sql's "ALL TABLES IN SCHEMA public" grant is a one-time
-- snapshot — it already ran before this table existed, so btm_app needs its
-- own grant here. Every migration that creates a new table needs this line;
-- found the hard way when a fresh-DB run of test_cost_and_report.py hit
-- InsufficientPrivilegeError on this exact table.
GRANT SELECT, INSERT, UPDATE ON shareable_itinerary_reports TO btm_app;
