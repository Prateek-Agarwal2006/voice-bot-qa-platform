from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


@dataclass(frozen=True)
class Word:
    text: str
    start: float
    end: float
    channel_index: int
    speaker_id: str | None = None
    type: str = "word"


def to_plain(obj: Any) -> Any:
    """Recursively convert SDK / dataclass objects into JSON-serializable dicts."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, dict):
        return {k: to_plain(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_plain(item) for item in obj]
    if hasattr(obj, "model_dump"):
        return to_plain(obj.model_dump())
    if hasattr(obj, "dict"):
        return to_plain(obj.dict())
    if is_dataclass(obj) and not isinstance(obj, type):
        return to_plain(asdict(obj))
    if hasattr(obj, "__dict__"):
        return to_plain({k: v for k, v in vars(obj).items() if not k.startswith("_")})
    return str(obj)


def _token_from_scribe_entry(entry: dict[str, Any], *, channel_index: int) -> Word:
    return Word(
        text=entry["text"],
        start=float(entry["start"]),
        end=float(entry["end"]),
        channel_index=channel_index,
        speaker_id=entry.get("speaker_id"),
        type=entry.get("type", "word"),
    )


def words_from_scribe_payload(raw: dict[str, Any]) -> list[Word]:
    """Extract Scribe tokens preserving type and timestamps."""
    words: list[Word] = []

    if "words" in raw and raw["words"]:
        for entry in raw["words"]:
            channel_index = entry.get("channel_index")
            if channel_index is None:
                continue
            words.append(_token_from_scribe_entry(entry, channel_index=int(channel_index)))
        return sorted(words, key=lambda w: w.start)

    for transcript in raw.get("transcripts") or []:
        channel_index = int(transcript["channel_index"])
        for entry in transcript.get("words") or []:
            words.append(_token_from_scribe_entry(entry, channel_index=channel_index))

    return sorted(words, key=lambda w: w.start)
