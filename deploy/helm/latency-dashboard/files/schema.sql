-- Voice Bot QA Platform — Postgres schema
-- Run once against a fresh database. All statements are idempotent.

-- ── enums ──────────────────────────────────────────────────────────────────────

DO $$ BEGIN
    CREATE TYPE recording_status AS ENUM (
        'pending', 'downloading', 'transcribing', 'structuring', 'evaluating', 'done', 'failed'
    );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
    CREATE TYPE ingestion_source AS ENUM ('upload', 'https');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── latency_runs ───────────────────────────────────────────────────────────────
-- One row per atomic probe run (one target, one source region, one collection cycle).
-- samples JSONB stores the aggregate Sample (avg, p50, p95, etc.).

CREATE TABLE IF NOT EXISTS latency_runs (
    run_id         TEXT         PRIMARY KEY,
    collected_at   TIMESTAMPTZ  NOT NULL,
    source_region  TEXT         NOT NULL,
    target_id      TEXT         NOT NULL,
    model          TEXT         NOT NULL,
    config_version TEXT         NOT NULL,
    n              INTEGER      NOT NULL,
    timeout_ms     INTEGER      NOT NULL,
    samples        JSONB        NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_latency_runs_lookup
    ON latency_runs (source_region, model, target_id, collected_at DESC);

-- ── recordings ─────────────────────────────────────────────────────────────────
-- Job queue for the Eval Worker. One row per audio file submitted for evaluation.

CREATE TABLE IF NOT EXISTS recordings (
    recording_id     TEXT              PRIMARY KEY,
    status           recording_status  NOT NULL DEFAULT 'pending',
    ingestion_source ingestion_source  NOT NULL,
    source_url       TEXT,
    judge_model      TEXT              NOT NULL DEFAULT 'gpt-4o-mini',
    url_provider     TEXT              NOT NULL DEFAULT 'direct',
    error_message    TEXT,
    created_at       TIMESTAMPTZ       NOT NULL DEFAULT NOW(),
    updated_at       TIMESTAMPTZ       NOT NULL DEFAULT NOW()
);

-- Idempotent migration for clusters created before judge_model was added.
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS judge_model TEXT NOT NULL DEFAULT 'gpt-4o-mini';
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS url_provider TEXT NOT NULL DEFAULT 'direct';

-- Partial index: only pending rows are polled; keeps the scan tiny.
CREATE INDEX IF NOT EXISTS idx_recordings_pending
    ON recordings (created_at ASC) WHERE status = 'pending';

-- ── conversations ──────────────────────────────────────────────────────────────
-- Structured output of transcription + structuring stages.
-- turns and derived_signals are JSONB — queried as blobs, never column-by-column.

CREATE TABLE IF NOT EXISTS conversations (
    recording_id    TEXT         PRIMARY KEY REFERENCES recordings(recording_id),
    turns           JSONB        NOT NULL,
    derived_signals JSONB        NOT NULL,
    turn_count      INTEGER      NOT NULL,
    created_at      TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

-- ── evaluations ────────────────────────────────────────────────────────────────
-- Judge scores for one recording. Multiple rows allowed per recording
-- (different judge_model runs produce separate rows).

CREATE TABLE IF NOT EXISTS evaluations (
    evaluation_id  TEXT         PRIMARY KEY,
    recording_id   TEXT         NOT NULL REFERENCES recordings(recording_id),
    judge_model    TEXT         NOT NULL,
    dimensions     JSONB        NOT NULL,
    evaluated_at   TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_evaluations_recording
    ON evaluations (recording_id);
