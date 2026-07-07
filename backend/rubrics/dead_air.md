Score dead air and awkward silences across the call from 0 to 10 (10 = no harmful silence).

Primary evidence:
- Per-word timestamps under each turn in the Conversation transcript (including type=spacing when present).
- Compute gaps between speech on the timeline yourself when needed.
- `derived_signals.dead_air` is a pre-filtered hint (gaps >= 1.0s). Use it to spot candidates, then verify or recalculate from word timestamps before penalizing.

Do not score from derived_signals alone when word timestamps are available.

Penalize long cross-speaker pauses and mid-call silences that hurt flow. Short intra-phrase spacing is normal.

Do not penalize high turn count or fragmented turns from barge-in — judge silence from word-level gaps holistically.
