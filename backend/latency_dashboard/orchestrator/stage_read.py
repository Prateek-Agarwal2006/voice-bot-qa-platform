from __future__ import annotations

from typing import Any

from latency_dashboard.schemas import StageEventDTO

STATUS_LABEL: dict[str, str] = {
    "pending": "Queued",
    "downloading": "Downloading audio",
    "transcribing": "Transcribing",
    "structuring": "Building conversation",
    "evaluating": "Evaluating with judge",
    "done": "Complete",
    "failed": "Failed",
}


def _label(stage: str) -> str:
    return STATUS_LABEL.get(stage, stage)


def _iso(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def timeline_from_events(
    events: list[dict[str, Any]],
    *,
    current_status: str,
    error_message: str | None = None,
) -> list[StageEventDTO]:
    """Turn append-only DB events into UI timeline steps.

    Status updates are written when a stage *starts*. On failure we append a
    ``failed`` event — the stage that was in progress is the last non-failed
    event and should show as failed (not completed ✓).

    Recordings without stage events return an empty timeline (no legacy synthesize).
    """
    if not events:
        return []

    failed_detail = error_message
    pipeline_events: list[dict[str, Any]] = []
    for event in events:
        stage = str(event["stage"])
        if stage == "failed":
            failed_detail = event.get("detail") or error_message
            continue
        pipeline_events.append(event)

    if not pipeline_events:
        return [
            StageEventDTO(
                stage="failed",
                state="failed",
                label=_label("failed"),
                detail=failed_detail,
                at="",
            )
        ]

    steps: list[StageEventDTO] = []
    for index, event in enumerate(pipeline_events):
        stage = str(event["stage"])
        is_last = index == len(pipeline_events) - 1
        detail = event.get("detail")

        if stage == "done":
            state = "completed"
        elif current_status == "failed" and is_last:
            # Stage that was running when the exception was raised.
            state = "failed"
            detail = failed_detail
        elif is_last and current_status not in ("done", "failed"):
            state = "active"
        else:
            state = "completed"

        steps.append(
            StageEventDTO(
                stage=stage,
                state=state,
                label=_label(stage),
                detail=detail,
                at=_iso(event.get("created_at")),
            )
        )
    return steps


async def fetch_stage_events(conn: Any, recording_id: str) -> list[dict[str, Any]]:
    rows = await conn.fetch(
        """
        SELECT stage, detail, created_at
        FROM recording_stage_events
        WHERE recording_id = $1
        ORDER BY created_at ASC, id ASC
        """,
        recording_id,
    )
    return [dict(row) for row in rows]


async def fetch_stages_for_recording(
    conn: Any,
    recording_id: str,
    *,
    current_status: str,
    error_message: str | None = None,
) -> list[StageEventDTO]:
    events = await fetch_stage_events(conn, recording_id)
    return timeline_from_events(
        events,
        current_status=current_status,
        error_message=error_message,
    )


async def fetch_stages_for_many(
    conn: Any,
    recording_ids: list[str],
) -> dict[str, list[dict[str, Any]]]:
    if not recording_ids:
        return {}
    rows = await conn.fetch(
        """
        SELECT recording_id, stage, detail, created_at
        FROM recording_stage_events
        WHERE recording_id = ANY($1::text[])
        ORDER BY recording_id, created_at ASC, id ASC
        """,
        recording_ids,
    )
    grouped: dict[str, list[dict[str, Any]]] = {rid: [] for rid in recording_ids}
    for row in rows:
        grouped[row["recording_id"]].append(dict(row))
    return grouped
