-- 001_schema.sql — MedBalance-Q domain schema

-- ============================================================
-- Reference data
-- ============================================================

CREATE TABLE facility (
    id          TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    level       TEXT NOT NULL CHECK (level IN ('WH','DH','TH','CHC','PHC')),
    lat         DOUBLE PRECISION NOT NULL,
    lon         DOUBLE PRECISION NOT NULL,
    cold_storage_ok BOOLEAN NOT NULL DEFAULT true,
    cold_storage_note TEXT,
    report_format TEXT NOT NULL DEFAULT 'fhir' CHECK (report_format IN ('fhir','csv','chat','text')),
    report_lang TEXT NOT NULL DEFAULT 'en',
    taluk       TEXT,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE drug (
    code            TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    ven             CHAR(1) NOT NULL CHECK (ven IN ('V','E','N')),
    unit            TEXT NOT NULL,
    pack_size       INTEGER NOT NULL CHECK (pack_size > 0),
    cold_chain      BOOLEAN NOT NULL DEFAULT false,
    temp_min_c      DOUBLE PRECISION,
    temp_max_c      DOUBLE PRECISION,
    controlled      BOOLEAN NOT NULL DEFAULT false,
    min_residual_days INTEGER NOT NULL DEFAULT 30 CHECK (min_residual_days > 0),
    unit_cost_inr   NUMERIC(10,2) NOT NULL DEFAULT 0,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE drug_alias (
    id          SERIAL PRIMARY KEY,
    drug_code   TEXT NOT NULL REFERENCES drug(code),
    alias       TEXT NOT NULL,
    lang        TEXT NOT NULL DEFAULT 'en',
    source      TEXT,
    UNIQUE (drug_code, alias)
);
CREATE INDEX idx_drug_alias_alias ON drug_alias(alias);

CREATE TABLE route (
    id              SERIAL PRIMARY KEY,
    src_facility_id TEXT NOT NULL REFERENCES facility(id),
    dst_facility_id TEXT NOT NULL REFERENCES facility(id),
    distance_km     DOUBLE PRECISION NOT NULL CHECK (distance_km > 0),
    transit_hours   DOUBLE PRECISION NOT NULL CHECK (transit_hours > 0),
    cold_capable    BOOLEAN NOT NULL DEFAULT false,
    cost_ambient_inr NUMERIC(10,2) NOT NULL DEFAULT 0,
    cost_cold_inr   NUMERIC(10,2) NOT NULL DEFAULT 0,
    UNIQUE (src_facility_id, dst_facility_id)
);
CREATE INDEX idx_route_src ON route(src_facility_id);
CREATE INDEX idx_route_dst ON route(dst_facility_id);

CREATE TABLE vehicle (
    id              TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    type            TEXT NOT NULL CHECK (type IN ('cold_van','ambient_van','two_wheeler')),
    cold_chain      BOOLEAN NOT NULL DEFAULT false,
    capacity_units  INTEGER NOT NULL CHECK (capacity_units > 0),
    sensor_ids      TEXT[],
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ============================================================
-- Policy
-- ============================================================

CREATE TABLE policy (
    id                  SERIAL PRIMARY KEY,
    facility_id         TEXT NOT NULL REFERENCES facility(id),
    drug_code           TEXT NOT NULL REFERENCES drug(code),
    min_reserve_days    INTEGER NOT NULL DEFAULT 7 CHECK (min_reserve_days >= 0),
    target_days         INTEGER NOT NULL DEFAULT 21 CHECK (target_days > 0),
    max_stock_days      INTEGER NOT NULL DEFAULT 60 CHECK (max_stock_days > 0),
    lead_time_days      INTEGER NOT NULL DEFAULT 3 CHECK (lead_time_days >= 0),
    UNIQUE (facility_id, drug_code)
);
CREATE INDEX idx_policy_facility_drug ON policy(facility_id, drug_code);

-- ============================================================
-- Inventory
-- ============================================================

CREATE TABLE lot (
    id              SERIAL PRIMARY KEY,
    facility_id     TEXT NOT NULL REFERENCES facility(id),
    drug_code       TEXT NOT NULL REFERENCES drug(code),
    batch_no        TEXT NOT NULL,
    expiry          DATE NOT NULL,
    qty             INTEGER NOT NULL CHECK (qty >= 0),
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (facility_id, drug_code, batch_no)
);
CREATE INDEX idx_lot_facility_drug ON lot(facility_id, drug_code);
CREATE INDEX idx_lot_expiry ON lot(expiry);

-- ============================================================
-- Ingest / reports
-- ============================================================

CREATE TABLE stock_report (
    id              SERIAL PRIMARY KEY,
    facility_id     TEXT NOT NULL REFERENCES facility(id),
    reported_at     TIMESTAMPTZ NOT NULL,
    format          TEXT NOT NULL,
    raw_text        TEXT,
    raw_file_path   TEXT,
    llm_model       TEXT,
    prompt_ref      TEXT,
    confidence      DOUBLE PRECISION,
    status          TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','accepted','review','rejected')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_stock_report_facility ON stock_report(facility_id);

CREATE TABLE extraction_item (
    id              SERIAL PRIMARY KEY,
    report_id       INTEGER NOT NULL REFERENCES stock_report(id),
    drug_code       TEXT REFERENCES drug(code),
    drug_name_raw   TEXT NOT NULL,
    batch_no        TEXT,
    expiry          DATE,
    qty             INTEGER,
    unit            TEXT,
    confidence      DOUBLE PRECISION NOT NULL DEFAULT 0,
    flags           TEXT[] NOT NULL DEFAULT '{}',
    review_status   TEXT NOT NULL DEFAULT 'auto' CHECK (review_status IN ('auto','flagged','resolved','rejected')),
    resolved_by     TEXT,
    resolved_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_extraction_item_report ON extraction_item(report_id);

-- ============================================================
-- Consumption & forecast
-- ============================================================

CREATE TABLE consumption_daily (
    id              SERIAL PRIMARY KEY,
    facility_id     TEXT NOT NULL REFERENCES facility(id),
    drug_code       TEXT NOT NULL REFERENCES drug(code),
    date            DATE NOT NULL,
    qty             INTEGER NOT NULL CHECK (qty >= 0),
    UNIQUE (facility_id, drug_code, date)
);
CREATE INDEX idx_consumption_facility_drug ON consumption_daily(facility_id, drug_code);
CREATE INDEX idx_consumption_date ON consumption_daily(date);

CREATE TABLE forecast (
    id              SERIAL PRIMARY KEY,
    facility_id     TEXT NOT NULL REFERENCES facility(id),
    drug_code       TEXT NOT NULL REFERENCES drug(code),
    horizon_days    INTEGER NOT NULL,
    daily_rate      DOUBLE PRECISION NOT NULL,
    method          TEXT NOT NULL,
    confidence      DOUBLE PRECISION NOT NULL,
    context_multiplier DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    adjusted_rate   DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (facility_id, drug_code)
);
CREATE INDEX idx_forecast_facility_drug ON forecast(facility_id, drug_code);

-- ============================================================
-- Optimizer
-- ============================================================

CREATE TABLE plan_run (
    id              TEXT PRIMARY KEY,
    mode            TEXT NOT NULL DEFAULT 'live' CHECK (mode IN ('live','whatif','eval')),
    solver_tier     TEXT NOT NULL,
    energy          DOUBLE PRECISION,
    gap_to_milp     DOUBLE PRECISION,
    variables       INTEGER,
    constraints     INTEGER,
    transfers       INTEGER NOT NULL DEFAULT 0,
    shortage_reduction DOUBLE PRECISION,
    expiry_avoided  INTEGER,
    cost_inr        NUMERIC(10,2),
    params          JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE candidate (
    id              SERIAL PRIMARY KEY,
    plan_run_id     TEXT NOT NULL REFERENCES plan_run(id),
    chunk_id        TEXT,
    facility_id     TEXT NOT NULL REFERENCES facility(id),
    drug_code       TEXT NOT NULL REFERENCES drug(code),
    batch_no        TEXT NOT NULL,
    destination_id  TEXT NOT NULL REFERENCES facility(id),
    usable          INTEGER NOT NULL CHECK (usable >= 0),
    score           DOUBLE PRECISION NOT NULL,
    feasibility     JSONB,
    selected        BOOLEAN NOT NULL DEFAULT false,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_candidate_plan ON candidate(plan_run_id);

CREATE TABLE transfer_order (
    id              TEXT PRIMARY KEY,
    dta_number      TEXT NOT NULL UNIQUE,
    plan_run_id     TEXT NOT NULL REFERENCES plan_run(id),
    src_facility_id TEXT NOT NULL REFERENCES facility(id),
    dst_facility_id TEXT NOT NULL REFERENCES facility(id),
    drug_code       TEXT NOT NULL REFERENCES drug(code),
    drug_name       TEXT NOT NULL,
    batch_no        TEXT NOT NULL,
    qty             INTEGER NOT NULL CHECK (qty > 0),
    usable          INTEGER NOT NULL CHECK (usable >= 0),
    score           DOUBLE PRECISION,
    status          TEXT NOT NULL DEFAULT 'proposed'
                    CHECK (status IN ('proposed','approved','rejected','dispatched','in_transit','delivered','cancelled')),
    temperature_req TEXT NOT NULL DEFAULT 'ambient' CHECK (temperature_req IN ('ambient','cold_chain')),
    vehicle_id      TEXT REFERENCES vehicle(id),
    approved_by     TEXT,
    approved_at     TIMESTAMPTZ,
    rejected_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_order_plan ON transfer_order(plan_run_id);
CREATE INDEX idx_order_status ON transfer_order(status);
CREATE INDEX idx_order_src ON transfer_order(src_facility_id);
CREATE INDEX idx_order_dst ON transfer_order(dst_facility_id);

CREATE TABLE regret_entry (
    id              SERIAL PRIMARY KEY,
    plan_run_id     TEXT NOT NULL REFERENCES plan_run(id),
    order_id        TEXT REFERENCES transfer_order(id),
    alternative     TEXT NOT NULL,
    reason          TEXT NOT NULL,
    delta_score     DOUBLE PRECISION NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_regret_plan ON regret_entry(plan_run_id);

-- ============================================================
-- Custody / cold chain
-- ============================================================

CREATE TABLE custody_event (
    id              SERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL REFERENCES transfer_order(id),
    event_type      TEXT NOT NULL CHECK (event_type IN ('created','picked','dispatched','checkpoint','delivered','exception')),
    actor           TEXT NOT NULL,
    timestamp       TIMESTAMPTZ NOT NULL,
    location        TEXT,
    temperature_c   DOUBLE PRECISION,
    notes           TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_custody_order ON custody_event(order_id);

CREATE TABLE sensor_reading (
    id              SERIAL PRIMARY KEY,
    device_id       TEXT NOT NULL,
    vehicle_id      TEXT REFERENCES vehicle(id),
    temperature_c   DOUBLE PRECISION NOT NULL,
    humidity_pct    DOUBLE PRECISION,
    battery_pct     INTEGER,
    lat             DOUBLE PRECISION,
    lon             DOUBLE PRECISION,
    recorded_at     TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_sensor_device ON sensor_reading(device_id);
CREATE INDEX idx_sensor_vehicle ON sensor_reading(vehicle_id);
CREATE INDEX idx_sensor_time ON sensor_reading(recorded_at);

-- ============================================================
-- Credit memo
-- ============================================================

CREATE TABLE credit_memo (
    id              SERIAL PRIMARY KEY,
    order_id        TEXT NOT NULL REFERENCES transfer_order(id),
    amount_inr      NUMERIC(10,2) NOT NULL,
    src_facility_id TEXT NOT NULL REFERENCES facility(id),
    dst_facility_id TEXT NOT NULL REFERENCES facility(id),
    issued_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    pdf_path        TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_credit_memo_order ON credit_memo(order_id);

-- ============================================================
-- Audit log (hash chain)
-- ============================================================

CREATE TABLE audit_log (
    seq             SERIAL PRIMARY KEY,
    actor           TEXT NOT NULL,
    action          TEXT NOT NULL,
    entity          TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    payload         JSONB NOT NULL,
    hash            TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_audit_entity ON audit_log(entity, entity_id);

-- ============================================================
-- GenAI / LLM
-- ============================================================

CREATE TABLE llm_call (
    id              SERIAL PRIMARY KEY,
    purpose         TEXT NOT NULL,
    prompt_id       TEXT NOT NULL,
    version         INTEGER NOT NULL,
    model           TEXT NOT NULL,
    input           JSONB NOT NULL,
    output          JSONB,
    confidence      DOUBLE PRECISION,
    cached          BOOLEAN NOT NULL DEFAULT false,
    fallback        BOOLEAN NOT NULL DEFAULT false,
    latency_ms      INTEGER,
    cache_key       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_llm_call_purpose ON llm_call(purpose);
CREATE INDEX idx_llm_call_cache ON llm_call(cache_key);

CREATE TABLE chat_session (
    id              TEXT PRIMARY KEY DEFAULT 'cs-' || gen_random_uuid()::text,
    user_id         TEXT,
    context         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE chat_message (
    id              SERIAL PRIMARY KEY,
    session_id      TEXT NOT NULL REFERENCES chat_session(id),
    role            TEXT NOT NULL CHECK (role IN ('user','assistant','system')),
    content         TEXT NOT NULL,
    tool_calls      JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX idx_chat_message_session ON chat_message(session_id);
