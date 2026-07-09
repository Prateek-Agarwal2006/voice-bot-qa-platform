from __future__ import annotations

# Idempotent DDL for clusters that already ran an older schema.sql at first boot.
ENSURE_STAGE_EVENTS_SQL = """
CREATE TABLE IF NOT EXISTS recording_stage_events (
    id            BIGSERIAL PRIMARY KEY,
    recording_id  TEXT         NOT NULL REFERENCES recordings(recording_id) ON DELETE CASCADE,
    stage         TEXT         NOT NULL,
    detail        TEXT,
    created_at    TIMESTAMPTZ  NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_recording_stage_events_recording
    ON recording_stage_events (recording_id, created_at ASC);
"""


async def ensure_stage_events_table(conn) -> None:
    await conn.execute(ENSURE_STAGE_EVENTS_SQL)


ENSURE_SOURCE_FILENAME_SQL = """
ALTER TABLE recordings ADD COLUMN IF NOT EXISTS source_filename TEXT;
"""


async def ensure_source_filename_column(conn) -> None:
    await conn.execute(ENSURE_SOURCE_FILENAME_SQL)
