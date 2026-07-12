> **Deterministic dimension** — scored in code from word timestamps (`eval_worker/metrics.py`), not by the Judge. This file documents the scoring policy; thresholds live in `eval_worker/constants.py`. Editing this file does not change behaviour.

Response Latency measures how quickly the Voice Bot starts speaking after the Customer stops: for each bot reply, gap = first bot word start − last customer word end (computed in `conversation.py`, aggregated as p50/p95/max).

A bot that acknowledges fast ("One moment…") scores well here even if a lookup follows — the silent lookup itself is charged to Dead Air. Silence is never excused by its cause.

Scoring policy:

| p50 latency | score |
|---|---|
| ≤ 2.0s | 10 |
| ≤ 3.0s | 8 |
| ≤ 4.0s | 6 |
| ≤ 6.0s | 4 |
| slower | 2 |

Penalty: −2 if any single response gap exceeds 6.0s. Floor 0. Calls with no customer→bot exchanges score 10.
