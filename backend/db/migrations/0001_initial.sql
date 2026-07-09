-- Initial schema per specs/001-business-travel-manager/data-model.md

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE tenants (
    tenant_id           TEXT PRIMARY KEY,
    name                TEXT NOT NULL,
    travel_policy       JSONB NOT NULL DEFAULT '{}'::jsonb,
    seat_quota          INTEGER,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE users (
    user_id             TEXT PRIMARY KEY,       -- email
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    google_sub          TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_active_at      TIMESTAMPTZ
);

CREATE TABLE waitlist (
    email               TEXT PRIMARY KEY,
    status              TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'invited', 'active')),
    requested_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    invited_at          TIMESTAMPTZ,
    activation_token    TEXT,
    token_expires_at    TIMESTAMPTZ
);

CREATE TABLE sessions (
    session_id          TEXT PRIMARY KEY,
    user_id             TEXT NOT NULL REFERENCES users(user_id),
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    status              TEXT NOT NULL CHECK (status IN ('in_progress', 'awaiting_approval', 'confirmed', 'closed', 'abandoned')),
    trip_request        JSONB NOT NULL,
    itinerary           JSONB,
    total_cost_usd      NUMERIC(10, 4) NOT NULL DEFAULT 0,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    closed_at           TIMESTAMPTZ
);

CREATE TABLE research_options (
    option_id           TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    category            TEXT NOT NULL CHECK (category IN ('flight', 'accommodation')),
    attributes          JSONB NOT NULL,
    decision            TEXT NOT NULL DEFAULT 'pending' CHECK (decision IN ('pending', 'selected', 'rejected')),
    badge               TEXT CHECK (badge IN ('wishlisted', 'past_stay')),
    shown_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    decided_at          TIMESTAMPTZ
);

CREATE TABLE approval_events (
    event_id            TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    option_id           TEXT REFERENCES research_options(option_id),
    decision            TEXT NOT NULL CHECK (decision IN ('selected', 'rejected', 'itinerary_confirmed')),
    shown_snapshot       JSONB NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Append-only: constitution Principle X / spec NFR-05. No UPDATE or DELETE grant, ever.

CREATE TABLE conversation_turns (
    turn_id             TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    user_id             TEXT NOT NULL REFERENCES users(user_id),
    role                TEXT NOT NULL CHECK (role IN ('traveler', 'system')),
    content             TEXT NOT NULL,
    embedding           vector(1536),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE semantic_memories (
    preference_id       TEXT PRIMARY KEY,
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    user_id             TEXT NOT NULL REFERENCES users(user_id),
    type                TEXT NOT NULL CHECK (type IN ('seat', 'hotel_proximity', 'dietary', 'preferred_airline', 'budget_pattern')),
    value               JSONB NOT NULL,
    version             INTEGER NOT NULL,
    superseded_by       TEXT REFERENCES semantic_memories(preference_id),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE cost_events (
    event_id            TEXT PRIMARY KEY,
    session_id          TEXT NOT NULL REFERENCES sessions(session_id),
    tenant_id           TEXT NOT NULL REFERENCES tenants(tenant_id),
    user_id             TEXT NOT NULL REFERENCES users(user_id),
    agent_type          TEXT NOT NULL,
    model_id            TEXT NOT NULL,
    tokens_in           INTEGER NOT NULL DEFAULT 0,
    tokens_out          INTEGER NOT NULL DEFAULT 0,
    cost_usd            NUMERIC(10, 6) NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_conversation_turns_embedding ON conversation_turns USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_sessions_tenant_user ON sessions(tenant_id, user_id);
CREATE INDEX idx_cost_events_session ON cost_events(session_id);
CREATE INDEX idx_research_options_session ON research_options(session_id);
