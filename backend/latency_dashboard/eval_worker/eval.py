from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from deepeval.test_case import LLMTestCase, SingleTurnParams

from latency_dashboard.eval_worker.conversation import build_conversation
from latency_dashboard.eval_worker.downloader import download
from latency_dashboard.eval_worker.url_normalizer import normalize
from latency_dashboard.eval_worker.judge import build_judge_model, judge_model_label
from latency_dashboard.eval_worker.metrics import build_metrics
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


def _format_scribe_transcript(conversation: dict[str, Any]) -> str:
    channel_map = conversation.get("channel_map", {})
    lines = [
        "=== ElevenLabs Scribe transcript (stereo multichannel) ===",
        f"recording_id: {conversation.get('recording_id', 'unknown')}",
        f"channel_map: {channel_map}",
        "",
    ]
    for turn in conversation.get("turns", []):
        speaker = turn.get("speaker", "Unknown")
        start, end = turn.get("start"), turn.get("end")
        timing = f" [{start:.1f}s–{end:.1f}s]" if isinstance(start, (int, float)) and isinstance(end, (int, float)) else ""
        lines.append(f"{speaker}{timing}: {turn.get('text', '')}")
    lines.append("=== end transcript ===")
    return "\n".join(lines)


def _format_timing_transcript(conversation: dict[str, Any], words) -> str:
    import json as _json
    lines = [
        "=== Recorded call with word timestamps (Customer ↔ Voice Bot) ===",
        f"recording_id: {conversation.get('recording_id', 'unknown')}",
        "",
    ]
    latency_by_turn = {
        int(item["before_voice_bot_turn_index"]): float(item["seconds"])
        for item in conversation.get("derived_signals", {}).get("bot_response_latencies", [])
    }
    for turn in conversation.get("turns", []):
        speaker = turn.get("speaker", "Unknown")
        start, end = turn.get("start"), turn.get("end")
        timing = f" [{start:.1f}s–{end:.1f}s]" if isinstance(start, (int, float)) and isinstance(end, (int, float)) else ""
        lines.append(f"{speaker}{timing}: {turn.get('text', '')}")
        turn_words = [
            w for w in words
            if w.channel_index == turn["channel_index"] and turn["start"] <= w.start < turn["end"]
        ]
        if turn_words:
            lines.append("  words:")
            for w in turn_words:
                lines.append(f'    [{w.start:.2f}–{w.end:.2f}] "{w.text}"')
        turn_idx = int(turn.get("turn_index", -1))
        if turn_idx in latency_by_turn:
            lines.append(f"  response_latency_seconds: {latency_by_turn[turn_idx]:.3f}")
        lines.append("")
    signals = conversation.get("derived_signals", {})
    if signals:
        lines.append("=== derived_signals ===")
        lines.append(_json.dumps(signals, indent=2))
        lines.append("=== end derived_signals ===")
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
    return result


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

        await update_recording_status(recording_id, "transcribing")
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
        timing_tc = LLMTestCase(input="", actual_output=_format_timing_transcript(conversation, words))
        dimensions: dict[str, Any] = {}

        for dimension_key, metric_kind, metric, test_case_kind in build_metrics(judge, verbose=False):
            test_case = narrative_tc if test_case_kind == "llm" else timing_tc
            metric.measure(test_case)
            dimensions[dimension_key] = _build_dimension_result(
                dimension_key=dimension_key,
                metric_kind=metric_kind,
                metric=metric,
            )

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
