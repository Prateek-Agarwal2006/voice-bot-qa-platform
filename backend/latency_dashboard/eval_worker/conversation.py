from __future__ import annotations

from latency_dashboard.eval_worker.constants import (
    CHANNEL_LABEL,
    CUSTOMER_CHANNEL,
    DEAD_AIR_MIN_GAP_SEC,
    HESITATION_MIN_GAP_SEC,
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
    return {
        "bot_response_latencies": _bot_response_latencies(turns),
        "customer_hesitations": _customer_hesitations(words),
        "dead_air": _dead_air(words),
        "interruptions": _interruptions(words),
    }


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
                overlap = round(min(customer_word.end, bot_word.end) - bot_word.start, 3)
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
