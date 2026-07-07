Score bot response latency across the call from 0 to 10 (10 = consistently fast responses, no egregious delays).

Primary evidence:
- Per-word start/end timestamps under each turn in the Conversation transcript.
- Compute gap = first Voice Bot word start minus last Customer word end for each bot reply.
- `response_latency_seconds` on Voice Bot turns and `derived_signals.bot_response_latencies` are hints only. If they disagree with word timestamps, trust timestamps.

Score high if latencies are generally under 4 seconds with no egregious outlier above 6 seconds. Score low if multiple slow responses or any very long gap clearly hurt the call.

Do not penalize turn splits from barge-in or ASR artifacts — judge latency from word times across the full call.
