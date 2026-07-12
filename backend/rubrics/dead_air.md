> **Deterministic dimension** — scored in code from word timestamps (`eval_worker/metrics.py`), not by the Judge. This file documents the scoring policy; thresholds live in `eval_worker/constants.py`. Editing this file does not change behaviour.

Dead Air measures silences ≥ 1.0s between consecutive words on the call timeline, **excluding** customer→bot response gaps (those are charged to Response Latency — the same silence is never penalised twice). Silences inside bot speech (e.g. during a lookup after "one moment") and bot→customer gaps count.

Scoring policy (total dead-air seconds across the call):

| total | score |
|---|---|
| 0s | 10 |
| ≤ 3s | 9 |
| ≤ 6s | 7 |
| ≤ 12s | 5 |
| ≤ 20s | 3 |
| more | 1 |

Penalty: −1 if any single silence reaches 5.0s. Floor 0.
