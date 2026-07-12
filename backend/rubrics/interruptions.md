> **Deterministic dimension** — scored in code from word timestamps (`eval_worker/metrics.py`), not by the Judge. This file documents the scoring policy; thresholds live in `eval_worker/constants.py`. Editing this file does not change behaviour.

Interruptions measures overlapping speech and turn-taking discipline from cross-channel word timestamps:

- **Bot-over-customer overlap**: word-level overlaps merged into episodes (gaps ≤ 1.0s join); total overlap seconds scored.
- **Barge-in recovery**: when the Customer starts speaking while the bot is mid-speech, the bot should yield within 1.0s. Each failure to yield is penalised.

Scoring policy (total bot-over-customer overlap seconds):

| total overlap | score |
|---|---|
| 0s | 10 |
| ≤ 0.5s | 9 |
| ≤ 1.5s | 7 |
| ≤ 3.0s | 5 |
| ≤ 6.0s | 3 |
| more | 1 |

Penalty: −1 per barge-in where the bot kept talking > 1.0s after customer onset (capped at −2). Floor 0.
