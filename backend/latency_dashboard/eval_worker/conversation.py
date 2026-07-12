from __future__ import annotations

import math

from latency_dashboard.eval_worker.constants import (
    BARGE_IN_YIELD_OK_SEC,
    BOT_SEGMENT_MERGE_GAP_SEC,
    CHANNEL_LABEL,
    CUSTOMER_CHANNEL,
    CUSTOMER_ONSET_MIN_GAP_SEC,
    DEAD_AIR_MIN_GAP_SEC,
    HESITATION_MIN_GAP_SEC,
    INTERRUPTION_EPISODE_MERGE_GAP_SEC,
    VOICE_BOT_CHANNEL,
)
from latency_dashboard.eval_worker.serialize import Word


def _speech_tokens(words: list[Word]) -> list[Word]:
    return [token for token in words if token.type == "word"]


def build_turns(words: list[Word]) -> list[dict]:
    turns: list[dict] = []
    current: dict | None = None

    for token in words:
        speaker = CHANNEL_LABEL.get(token.channel_index, f"speaker_{token.channel_index}")
        if current is None or current["channel_index"] != token.channel_index:
            if current is not None:
                turns.append(current)
            current = {
                "speaker": speaker,
                "channel_index": token.channel_index,
                "start": token.start,
                "end": token.end,
                "text": token.text,
            }
        else:
            current["text"] += token.text
            current["end"] = token.end

    if current is not None:
        turns.append(current)

    for index, turn in enumerate(turns):
        turn["turn_index"] = index

    return turns


def compute_derived_signals(words: list[Word], turns: list[dict]) -> dict:
    signals = {
        "bot_response_latencies": _bot_response_latencies(turns),
        "customer_hesitations": _customer_hesitations(words),
        "dead_air": _dead_air(words),
        "interruptions": _interruptions(words),
        "barge_in_recovery": _barge_in_recovery(words),
    }
    signals["aggregates"] = compute_timing_aggregates(signals)
    return signals


def _bot_response_latencies(turns: list[dict]) -> list[dict]:
    latencies: list[dict] = []
    for index, turn in enumerate(turns):
        if turn["channel_index"] != CUSTOMER_CHANNEL:
            continue
        next_bot = next(
            (t for t in turns[index + 1:] if t["channel_index"] == VOICE_BOT_CHANNEL),
            None,
        )
        if next_bot is None:
            continue
        gap = round(next_bot["start"] - turn["end"], 3)
        if gap < 0:
            continue
        latencies.append({
            "after_customer_turn_index": turn["turn_index"],
            "before_voice_bot_turn_index": next_bot["turn_index"],
            "seconds": gap,
            "customer_turn_end": turn["end"],
            "voice_bot_turn_start": next_bot["start"],
        })
    return latencies


def _customer_hesitations(words: list[Word]) -> list[dict]:
    customer_words = [w for w in _speech_tokens(words) if w.channel_index == CUSTOMER_CHANNEL]
    hesitations: list[dict] = []
    for previous, current in zip(customer_words, customer_words[1:]):
        gap = round(current.start - previous.end, 3)
        if gap >= HESITATION_MIN_GAP_SEC:
            hesitations.append({
                "seconds": gap,
                "after_word_end": previous.end,
                "before_word_start": current.start,
                "after_text": previous.text,
                "before_text": current.text,
            })
    return hesitations


def _dead_air(words: list[Word]) -> list[dict]:
    if len(words) < 2:
        return []
    segments: list[dict] = []
    for previous, current in zip(words, words[1:]):
        # Customer→bot gaps are response latency, scored by that dimension —
        # counting them here would penalise the same silence twice.
        if previous.channel_index == CUSTOMER_CHANNEL and current.channel_index == VOICE_BOT_CHANNEL:
            continue
        gap = round(current.start - previous.end, 3)
        if gap >= DEAD_AIR_MIN_GAP_SEC:
            segments.append({
                "seconds": gap,
                "start": previous.end,
                "end": current.start,
                "after": {"speaker": CHANNEL_LABEL.get(previous.channel_index, f"speaker_{previous.channel_index}"), "text": previous.text},
                "before": {"speaker": CHANNEL_LABEL.get(current.channel_index, f"speaker_{current.channel_index}"), "text": current.text},
            })
    return segments


def _interruptions(words: list[Word]) -> list[dict]:
    interruptions: list[dict] = []
    speech = _speech_tokens(words)
    for customer_word in speech:
        if customer_word.channel_index != CUSTOMER_CHANNEL:
            continue
        for bot_word in speech:
            if bot_word.channel_index != VOICE_BOT_CHANNEL:
                continue
            if bot_word.start >= customer_word.end:
                break
            if bot_word.start < customer_word.end and bot_word.end > customer_word.start:
                overlap = round(
                    min(customer_word.end, bot_word.end)
                    - max(customer_word.start, bot_word.start),
                    3,
                )
                if overlap > 0:
                    interruptions.append({
                        "overlap_seconds": overlap,
                        "customer_word": customer_word.text,
                        "voice_bot_word": bot_word.text,
                        "customer_start": customer_word.start,
                        "customer_end": customer_word.end,
                        "voice_bot_start": bot_word.start,
                        "voice_bot_end": bot_word.end,
                    })
    return interruptions


def _barge_in_recovery(words: list[Word]) -> list[dict]:
    """Customer starts speaking while the bot is mid-speech: how long did the bot keep talking?"""
    speech = _speech_tokens(words)

    bot_segments: list[dict] = []
    for token in speech:
        if token.channel_index != VOICE_BOT_CHANNEL:
            continue
        if bot_segments and token.start - bot_segments[-1]["end"] <= BOT_SEGMENT_MERGE_GAP_SEC:
            bot_segments[-1]["end"] = max(bot_segments[-1]["end"], token.end)
        else:
            bot_segments.append({"start": token.start, "end": token.end})

    events: list[dict] = []
    previous_customer_end: float | None = None
    for token in speech:
        if token.channel_index != CUSTOMER_CHANNEL:
            continue
        is_onset = (
            previous_customer_end is None
            or token.start - previous_customer_end >= CUSTOMER_ONSET_MIN_GAP_SEC
        )
        if is_onset:
            segment = next(
                (s for s in bot_segments if s["start"] < token.start < s["end"]),
                None,
            )
            if segment is not None:
                events.append({
                    "customer_onset": token.start,
                    "bot_stopped_at": segment["end"],
                    "bot_kept_talking_seconds": round(segment["end"] - token.start, 3),
                })
        previous_customer_end = token.end
    return events


def _percentile(sorted_values: list[float], fraction: float) -> float:
    if not sorted_values:
        return 0.0
    index = min(len(sorted_values) - 1, max(0, math.ceil(fraction * len(sorted_values)) - 1))
    return sorted_values[index]


def _interruption_episodes(interruptions: list[dict]) -> list[dict]:
    episodes: list[dict] = []
    for item in sorted(interruptions, key=lambda i: i["voice_bot_start"]):
        if (
            episodes
            and item["voice_bot_start"] - episodes[-1]["end"] <= INTERRUPTION_EPISODE_MERGE_GAP_SEC
        ):
            episodes[-1]["end"] = max(episodes[-1]["end"], item["voice_bot_end"])
            episodes[-1]["overlap_seconds"] = round(
                episodes[-1]["overlap_seconds"] + item["overlap_seconds"], 3
            )
        else:
            episodes.append({
                "start": item["voice_bot_start"],
                "end": item["voice_bot_end"],
                "overlap_seconds": item["overlap_seconds"],
            })
    return episodes


def compute_timing_aggregates(signals: dict) -> dict:
    latencies = sorted(item["seconds"] for item in signals["bot_response_latencies"])
    dead_air = [segment["seconds"] for segment in signals["dead_air"]]
    episodes = _interruption_episodes(signals["interruptions"])
    failed_yields = [
        event for event in signals["barge_in_recovery"]
        if event["bot_kept_talking_seconds"] > BARGE_IN_YIELD_OK_SEC
    ]
    return {
        "latency_count": len(latencies),
        "latency_p50_seconds": round(_percentile(latencies, 0.5), 3),
        "latency_p95_seconds": round(_percentile(latencies, 0.95), 3),
        "latency_max_seconds": round(max(latencies), 3) if latencies else 0.0,
        "dead_air_event_count": len(dead_air),
        "dead_air_total_seconds": round(sum(dead_air), 3),
        "dead_air_max_seconds": round(max(dead_air), 3) if dead_air else 0.0,
        "interruption_episode_count": len(episodes),
        "interruption_overlap_total_seconds": round(
            sum(episode["overlap_seconds"] for episode in episodes), 3
        ),
        "barge_in_count": len(signals["barge_in_recovery"]),
        "barge_in_failed_yield_count": len(failed_yields),
    }


def build_conversation(
    *,
    recording_id: str,
    source_url: str,
    raw_scribe: dict,
    words: list[Word],
) -> dict:
    turns = build_turns(words)
    return {
        "recording_id": recording_id,
        "source_url": source_url,
        "language_code": raw_scribe.get("language_code"),
        "language_probability": raw_scribe.get("language_probability"),
        "channel_map": {
            "0": CHANNEL_LABEL[CUSTOMER_CHANNEL],
            "1": CHANNEL_LABEL[VOICE_BOT_CHANNEL],
        },
        "turns": turns,
        "derived_signals": compute_derived_signals(words, turns),
        "token_count": len(words),
        "word_count": sum(1 for token in words if token.type == "word"),
        "turn_count": len(turns),
    }
