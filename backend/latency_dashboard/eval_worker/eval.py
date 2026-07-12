from __future__ import annotations

import asyncio
import uuid
from datetime import UTC, datetime
from typing import Any

from deepeval.test_case import LLMTestCase

from latency_dashboard.eval_worker.constants import TRANSCRIPT_CONFIDENCE_MIN
from latency_dashboard.eval_worker.conversation import build_conversation
from latency_dashboard.eval_worker.downloader import download
from latency_dashboard.eval_worker.url_normalizer import normalize
from latency_dashboard.eval_worker.judge import build_judge_model, judge_model_label
from latency_dashboard.eval_worker.metrics import DeterministicScore, build_metrics
from latency_dashboard.eval_worker.postgres_write import (
    update_recording_status,
    write_conversation,
    write_evaluation,
)
from latency_dashboard.eval_worker.scribe import transcribe_bytes
from latency_dashboard.eval_worker.serialize import words_from_scribe_payload
from latency_dashboard.eval_worker.staged_audio import delete_staged_audio

STORED_SCORE_MAX = 1.0
JUDGE_SCORE_MAX = 10


def _timing_summary_lines(conversation: dict[str, Any]) -> list[str]:
    agg = conversation.get("derived_signals", {}).get("aggregates")
    if not agg:
        return []
    return [
        "=== timing summary (computed from word timestamps — trust these numbers) ===",
        (
            f"bot response latency: n={agg['latency_count']}, "
            f"p50={agg['latency_p50_seconds']:.2f}s, p95={agg['latency_p95_seconds']:.2f}s, "
            f"max={agg['latency_max_seconds']:.2f}s"
        ),
        (
            f"dead air (silences >= 1.0s, response gaps excluded): "
            f"{agg['dead_air_event_count']} event(s), total {agg['dead_air_total_seconds']:.1f}s, "
            f"longest {agg['dead_air_max_seconds']:.1f}s"
        ),
        (
            f"interruptions: {agg['interruption_episode_count']} overlap episode(s), "
            f"total bot-over-customer overlap {agg['interruption_overlap_total_seconds']:.2f}s"
        ),
        (
            f"customer barge-ins: {agg['barge_in_count']}; "
            f"bot kept talking > 1.0s after onset: {agg['barge_in_failed_yield_count']}"
        ),
        "=== end timing summary ===",
    ]


def _format_scribe_transcript(conversation: dict[str, Any]) -> str:
    channel_map = conversation.get("channel_map", {})
    lines = [
        "=== Recorded call transcript (ASR, stereo multichannel) ===",
        f"recording_id: {conversation.get('recording_id', 'unknown')}",
        f"channel_map: {channel_map}",
        "Note: transcript produced by automatic speech recognition and may contain transcription errors.",
        "",
    ]
    for turn in conversation.get("turns", []):
        speaker = turn.get("speaker", "Unknown")
        start, end = turn.get("start"), turn.get("end")
        timing = f" [{start:.1f}s–{end:.1f}s]" if isinstance(start, (int, float)) and isinstance(end, (int, float)) else ""
        lines.append(f"[{turn.get('turn_index', '?')}] {speaker}{timing}: {turn.get('text', '')}")
    lines.append("")
    lines.extend(_timing_summary_lines(conversation))
    lines.append("=== end transcript ===")
    return "\n".join(lines)


def _build_dimension_result(*, dimension_key: str, metric_kind: str, metric: Any) -> dict[str, Any]:
    result: dict[str, Any] = {
        "score": metric.score,
        "score_max": STORED_SCORE_MAX,
        "rationale": metric.reason,
        "success": metric.success,
        "metric": metric_kind,
        "name": getattr(metric, "name", dimension_key),
    }
    if metric_kind == "geval" and isinstance(metric.score, (int, float)):
        result["judge_score"] = round(metric.score * JUDGE_SCORE_MAX, 1)
        result["judge_score_max"] = JUDGE_SCORE_MAX
    violations = getattr(metric, "violations", None)
    if violations:
        result["violations"] = violations
    # Only store outcome for metrics that declare outcome_labels (i.e. call_outcome).
    # The judge fills the optional field for other metrics too — ignore it there.
    outcome = getattr(metric, "outcome", None)
    if outcome and getattr(metric, "outcome_labels", []):
        result["outcome"] = outcome
    return result


def _deterministic_dimension_result(outcome: DeterministicScore) -> dict[str, Any]:
    return {
        "score": outcome.score,
        "score_max": STORED_SCORE_MAX,
        "rationale": outcome.reason,
        "success": outcome.success,
        "metric": "deterministic",
        "name": outcome.name,
    }


def _evaluation_meta(conversation: dict[str, Any]) -> dict[str, Any]:
    language_probability = conversation.get("language_probability")
    if isinstance(language_probability, (int, float)):
        level = "low" if language_probability < TRANSCRIPT_CONFIDENCE_MIN else "ok"
    else:
        level = "unknown"
    return {
        "transcript_confidence": {
            "language_probability": language_probability,
            "level": level,
        },
        "language_code": conversation.get("language_code"),
    }


async def run(
    recording_id: str,
    source_url: str,
    judge_model: str,
    url_provider: str = "direct",
    ingestion_source: str = "https",
) -> None:
    """Full eval pipeline for one recording: download → transcribe → structure → judge → write."""
    conversation_written = False
    past_structuring = False

    try:
        # Status already set to downloading by collector claim (atomic SKIP LOCKED).
        audio_bytes = await download(normalize(source_url, url_provider))
        print(f"[eval] downloaded {len(audio_bytes)} bytes, magic={audio_bytes[:8].hex()}", flush=True)

        await update_recording_status(recording_id, "transcribing")  #while updating here we dont need lock as its already handled in collector.
        raw_scribe = transcribe_bytes(audio_bytes)
        words = words_from_scribe_payload(raw_scribe)

        await update_recording_status(recording_id, "structuring")
        conversation = build_conversation(
            recording_id=recording_id,
            source_url=source_url,
            raw_scribe=raw_scribe,
            words=words,
        )
        past_structuring = True
        await write_conversation(recording_id, conversation)
        conversation_written = True

        if ingestion_source == "upload":
            await delete_staged_audio(recording_id)

        await update_recording_status(recording_id, "evaluating")
        judge = build_judge_model(model=judge_model)
        narrative_tc = LLMTestCase(input="", actual_output=_format_scribe_transcript(conversation))
        dimensions: dict[str, Any] = {}

        all_metrics = build_metrics(judge, verbose=False)

        # Score deterministic dimensions immediately (no I/O).
        for dimension_key, metric_kind, metric, _input_kind in all_metrics:
            if metric_kind == "deterministic":
                dimensions[dimension_key] = _deterministic_dimension_result(metric(conversation))

        # Run all GEval dimensions concurrently — each makes 2 LLM calls, so
        # sequential execution multiplies latency by the number of dimensions.
        geval_entries = [
            (key, kind, m, ik)
            for key, kind, m, ik in all_metrics
            if kind != "deterministic"
        ]

        async def _run_one(dimension_key: str, metric_kind: str, metric: Any) -> tuple[str, dict]:
            await metric.a_measure(narrative_tc)
            return dimension_key, _build_dimension_result(
                dimension_key=dimension_key,
                metric_kind=metric_kind,
                metric=metric,
            )

        results = await asyncio.gather(*[
            _run_one(key, kind, m) for key, kind, m, _ in geval_entries
        ])
        for dim_key, dim_result in results:
            dimensions[dim_key] = dim_result

        # Call-level metadata; underscore key is skipped by the UI's dimension list.
        dimensions["_meta"] = _evaluation_meta(conversation)

        result = {
            "recording_id": recording_id,
            "evaluated_at": datetime.now(UTC).isoformat(),
            "judge_model": judge_model_label(judge),
            "dimensions": dimensions,
        }
        await write_evaluation(recording_id, result, evaluation_id=str(uuid.uuid4()))
        await update_recording_status(recording_id, "done")

    except Exception as exc:
        if ingestion_source == "upload" and (conversation_written or past_structuring):
            await delete_staged_audio(recording_id)
        await update_recording_status(recording_id, "failed", error_message=str(exc))
        raise
