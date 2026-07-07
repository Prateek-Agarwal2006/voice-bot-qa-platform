from __future__ import annotations

import io
import os
from typing import Any

from elevenlabs import ElevenLabs

from latency_dashboard.eval_worker.constants import SCRIBE_MODEL_ID
from latency_dashboard.eval_worker.serialize import to_plain


def transcribe_bytes(audio_bytes: bytes, *, api_key: str | None = None) -> dict[str, Any]:
    """Call ElevenLabs Scribe multichannel API with raw audio bytes."""
    key = api_key or os.environ.get("ELEVENLABS_API_KEY")
    if not key:
        raise RuntimeError("ELEVENLABS_API_KEY is not set.")

    client = ElevenLabs(api_key=key)
    result = client.speech_to_text.convert(
        file=("recording.mp3", io.BytesIO(audio_bytes), "audio/mpeg"),
        model_id=SCRIBE_MODEL_ID,
        use_multi_channel=True,
        multichannel_output_style="combined",
        diarize=False,
        timestamps_granularity="word",
    )
    return to_plain(result)
