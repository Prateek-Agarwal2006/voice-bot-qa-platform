"""E1/E3 eval scoring: rubric band parsing, derived signals, deterministic scorers."""

from __future__ import annotations

import pytest

from latency_dashboard.eval_worker.conversation import (
    _barge_in_recovery,
    _dead_air,
    _interruption_episodes,
    build_turns,
    compute_derived_signals,
)
from latency_dashboard.eval_worker.serialize import Word

try:  # metrics.py needs the eval-worker extras (deepeval); conversation tests don't.
    from latency_dashboard.eval_worker.metrics import (
        RUBRICS_DIR,
        load_rubric_spec,
        parse_rubric_markdown,
        score_dead_air,
        score_interruptions,
        score_response_latency,
    )
    HAS_EVAL_DEPS = True
except ImportError:
    HAS_EVAL_DEPS = False

needs_eval_deps = pytest.mark.skipif(
    not HAS_EVAL_DEPS, reason="deepeval not installed (eval-worker extra)"
)


def customer(text: str, start: float, end: float) -> Word:
    return Word(text=text, start=start, end=end, channel_index=0)


def bot(text: str, start: float, end: float) -> Word:
    return Word(text=text, start=start, end=end, channel_index=1)


def conversation_for(words: list[Word]) -> dict:
    turns = build_turns(words)
    return {"derived_signals": compute_derived_signals(words, turns)}


# ── derived signals (E3) ──────────────────────────────────────────────────────


def test_dead_air_excludes_customer_to_bot_response_gap():
    words = [
        customer("hello", 0.0, 0.5),
        bot("hi", 3.5, 4.0),           # 3.0s customer→bot gap = response latency, not dead air
        bot("there", 9.0, 9.5),        # 5.0s bot→bot gap = dead air
    ]
    segments = _dead_air(words)
    assert len(segments) == 1
    assert segments[0]["seconds"] == pytest.approx(5.0)


def test_barge_in_recovery_measures_bot_yield_time():
    words = [
        bot("our", 0.0, 0.4),
        bot("opening", 0.5, 1.0),
        bot("hours", 1.1, 1.6),
        bot("are", 1.7, 4.0),
        customer("wait", 2.0, 2.4),    # onset while bot segment [0.0–4.0] is running
    ]
    events = _barge_in_recovery(words)
    assert len(events) == 1
    assert events[0]["bot_kept_talking_seconds"] == pytest.approx(2.0)


def test_no_barge_in_when_customer_speaks_in_silence():
    words = [
        bot("hello", 0.0, 0.5),
        customer("hi", 2.0, 2.3),
    ]
    assert _barge_in_recovery(words) == []


def test_interruption_episodes_merge_adjacent_word_overlaps():
    interruptions = [
        {"voice_bot_start": 1.0, "voice_bot_end": 1.3, "overlap_seconds": 0.3},
        {"voice_bot_start": 1.4, "voice_bot_end": 1.8, "overlap_seconds": 0.4},   # merges (gap 0.1)
        {"voice_bot_start": 5.0, "voice_bot_end": 5.2, "overlap_seconds": 0.2},   # separate episode
    ]
    episodes = _interruption_episodes(interruptions)
    assert len(episodes) == 2
    assert episodes[0]["overlap_seconds"] == pytest.approx(0.7)


def test_aggregates_present_in_derived_signals():
    words = [customer("hello", 0.0, 0.5), bot("hi", 1.0, 1.4)]
    signals = compute_derived_signals(words, build_turns(words))
    agg = signals["aggregates"]
    assert agg["latency_count"] == 1
    assert agg["latency_p50_seconds"] == pytest.approx(0.5)
    assert agg["dead_air_event_count"] == 0


# ── rubric band parsing (E1) ──────────────────────────────────────────────────


@needs_eval_deps
def test_parse_bands_and_sections():
    spec = parse_rubric_markdown(
        "Criteria text here.\n\n"
        "## Bands\n- 9-10: great\n- 5-8: ok\n- 0-4: bad\n\n"
        "## Violation types\n- some_issue: a description\n"
    )
    assert spec.criteria == "Criteria text here."
    assert [r.score_range for r in spec.bands] == [(0, 4), (5, 8), (9, 10)]
    assert spec.violation_types == [{"type": "some_issue", "description": "a description"}]


@needs_eval_deps
def test_bands_must_cover_zero_to_ten():
    with pytest.raises(RuntimeError, match="start at 0"):
        parse_rubric_markdown("x\n## Bands\n- 9-10: great\n- 2-8: ok\n")


@needs_eval_deps
def test_bands_must_be_contiguous():
    with pytest.raises(RuntimeError, match="contiguous"):
        parse_rubric_markdown("x\n## Bands\n- 9-10: great\n- 6-8: ok\n- 0-4: bad\n")


@needs_eval_deps
def test_missing_bands_section_returns_none():
    spec = parse_rubric_markdown("Only criteria, no bands.")
    assert spec.bands is None


@needs_eval_deps
@pytest.mark.parametrize(
    "name",
    [
        "task_success",
        "conversation_quality",
        "response_alignment",
        "user_disappointment",
        "conversation_progression",
        "faithfulness",
        "sentiment_trajectory",
        "call_outcome",
    ],
)
def test_shipped_rubrics_parse_with_full_band_coverage(name):
    assert (RUBRICS_DIR / f"{name}.md").exists()
    spec = load_rubric_spec(name, fallback="unused")
    assert spec.bands, f"{name}.md must define score bands"
    assert spec.criteria


@needs_eval_deps
def test_call_outcome_rubric_declares_labels():
    spec = load_rubric_spec("call_outcome", fallback="unused")
    labels = {entry["label"] for entry in spec.outcome_labels}
    assert "resolved" in labels and "escalated" in labels


# ── deterministic scorers (E3) ────────────────────────────────────────────────


@needs_eval_deps
def test_fast_clean_call_scores_ten_everywhere():
    words = [
        customer("hello", 0.0, 0.5),
        bot("hi", 1.0, 1.4),
        customer("thanks", 2.0, 2.4),
        bot("welcome", 3.0, 3.4),
    ]
    conv = conversation_for(words)
    assert score_response_latency(conv).judge_score == 10
    assert score_dead_air(conv).judge_score == 10
    assert score_interruptions(conv).judge_score == 10


@needs_eval_deps
def test_slow_call_scores_low_latency_with_outlier_penalty():
    words = [
        customer("hello", 0.0, 0.5),
        bot("hi", 8.0, 8.4),            # 7.5s gap: p50 band ≤6s fails → floor 2, outlier −2
    ]
    result = score_response_latency(conversation_for(words))
    assert result.judge_score == 0
    assert not result.success
    assert "p50=7.50s" in result.reason


@needs_eval_deps
def test_dead_air_penalises_long_bot_silence():
    words = [
        customer("hello", 0.0, 0.5),
        bot("one", 1.0, 1.4),
        bot("moment", 7.6, 8.0),        # 6.2s silence inside bot speech
    ]
    result = score_dead_air(conversation_for(words))
    # total 6.2s → band ≤12 = 5, longest ≥5s → −1
    assert result.judge_score == 4
    assert "longest 6.2s" in result.reason


@needs_eval_deps
def test_interruptions_penalise_failed_yield():
    words = [
        bot("our", 0.0, 0.4),
        bot("hours", 0.5, 1.0),
        bot("are", 1.1, 1.5),
        bot("nine", 1.6, 4.5),
        customer("wait", 2.0, 2.5),     # overlap 0.5s with "nine"; bot talks 2.5s after onset
        customer("stop", 2.6, 3.0),
    ]
    result = score_interruptions(conversation_for(words))
    # overlap: "nine"[1.6-4.5] vs "wait"[2.0-2.5] = 0.5s, vs "stop"[2.6-3.0] = 0.4s → 0.9s ≤1.5 → 7
    # one failed yield (2.5s > 1.0s) → −1
    assert result.judge_score == 6
    assert "barge-in" in result.reason


@needs_eval_deps
def test_empty_call_scores_ten():
    conv = conversation_for([])
    assert score_response_latency(conv).judge_score == 10
    assert score_dead_air(conv).judge_score == 10
    assert score_interruptions(conv).judge_score == 10
