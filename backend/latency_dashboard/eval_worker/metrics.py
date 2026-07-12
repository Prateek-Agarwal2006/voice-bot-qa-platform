from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from deepeval.metrics.g_eval import Rubric
from deepeval.models import LiteLLMModel
from deepeval.test_case import SingleTurnParams

from latency_dashboard.eval_worker.constants import (
    BARGE_IN_YIELD_OK_SEC,
    DEAD_AIR_FLOOR_SCORE,
    DEAD_AIR_LONG_GAP_PENALTY,
    DEAD_AIR_LONG_GAP_SEC,
    DEAD_AIR_TOTAL_BANDS,
    FAILED_YIELD_PENALTY,
    FAILED_YIELD_PENALTY_MAX,
    LATENCY_FLOOR_SCORE,
    LATENCY_OUTLIER_PENALTY,
    LATENCY_OUTLIER_SEC,
    LATENCY_P50_BANDS,
    OVERLAP_FLOOR_SCORE,
    OVERLAP_TOTAL_BANDS,
)
from latency_dashboard.eval_worker.voice_geval import VoiceGEval

# rubrics/ lives at backend/rubrics/ — two levels up from eval_worker/
RUBRICS_DIR = Path(__file__).resolve().parent.parent.parent / "rubrics"

GEVAL_TRANSCRIPT_PARAMS = [SingleTurnParams.ACTUAL_OUTPUT]

TRANSCRIPT_HINT = (
    " The Conversation is the full ASR transcript of one recorded call (Customer ↔ Voice Bot), "
    "with numbered turns like [3] and a computed timing summary at the end. "
    "Score the entire call holistically — not isolated lines — and cite turn indices in findings. "
    "Trust the timing summary numbers; do not recompute timing yourself."
)

JUDGE_SCORE_MIN = 0
JUDGE_SCORE_MAX = 10

_BAND_LINE = re.compile(r"^-\s*(\d+)\s*[-–]\s*(\d+)\s*:\s*(.+)$")
_TYPED_LINE = re.compile(r"^-\s*([a-z0-9_]+)\s*:\s*(.+)$")


# ── Rubric markdown parsing (E1 / E4 / E5) ────────────────────────────────────


@dataclass(frozen=True)
class RubricSpec:
    """Parsed rubric .md: criteria prose, score bands, violation types, outcome labels."""

    criteria: str
    bands: list[Rubric] | None = None
    violation_types: list[dict[str, str]] = field(default_factory=list)
    outcome_labels: list[dict[str, str]] = field(default_factory=list)


def parse_rubric_markdown(text: str, *, source: str = "rubric") -> RubricSpec:
    sections: dict[str, list[str]] = {"criteria": []}
    current = "criteria"
    for line in text.splitlines():
        header = line.strip().lower()
        if header.startswith("## "):
            current = header[3:].strip()
            sections.setdefault(current, [])
            continue
        sections[current].append(line)

    criteria = "\n".join(sections["criteria"]).strip()
    bands = _parse_bands(sections.get("bands"), source=source)
    violation_types = _parse_typed_lines(sections.get("violation types"), key="type")
    outcome_labels = _parse_typed_lines(sections.get("outcome labels"), key="label")
    return RubricSpec(
        criteria=criteria,
        bands=bands,
        violation_types=violation_types,
        outcome_labels=outcome_labels,
    )


def _parse_bands(lines: list[str] | None, *, source: str) -> list[Rubric] | None:
    if lines is None:
        return None
    bands: list[tuple[int, int, str]] = []
    for line in lines:
        match = _BAND_LINE.match(line.strip())
        if match:
            bands.append((int(match.group(1)), int(match.group(2)), match.group(3).strip()))
    if not bands:
        return None

    # judge_score = normalised score × 10 only holds if bands cover 0-10 exactly.
    bands.sort(key=lambda band: band[0])
    if bands[0][0] != JUDGE_SCORE_MIN or bands[-1][1] != JUDGE_SCORE_MAX:
        raise RuntimeError(f"{source}: bands must start at {JUDGE_SCORE_MIN} and end at {JUDGE_SCORE_MAX}.")
    for (_, prev_end, _), (next_start, _, _) in zip(bands, bands[1:]):
        if next_start != prev_end + 1:
            raise RuntimeError(f"{source}: bands must be contiguous — gap or overlap at score {next_start}.")

    return [
        Rubric(score_range=(start, end), expected_outcome=outcome)
        for start, end, outcome in bands
    ]


def _parse_typed_lines(lines: list[str] | None, *, key: str) -> list[dict[str, str]]:
    if not lines:
        return []
    entries: list[dict[str, str]] = []
    for line in lines:
        match = _TYPED_LINE.match(line.strip())
        if match:
            entries.append({key: match.group(1), "description": match.group(2).strip()})
    return entries


def load_rubric_spec(name: str, *, fallback: str) -> RubricSpec:
    path = RUBRICS_DIR / f"{name}.md"
    if not path.exists():
        return RubricSpec(criteria=fallback)
    return parse_rubric_markdown(path.read_text(encoding="utf-8"), source=path.name)


def _narrative_geval(*, name: str, rubric_name: str, fallback: str, judge_model: LiteLLMModel, verbose: bool) -> VoiceGEval:
    spec = load_rubric_spec(rubric_name, fallback=fallback)
    return VoiceGEval(
        name=name,
        criteria=spec.criteria + TRANSCRIPT_HINT,
        rubric=spec.bands,
        model=judge_model,
        evaluation_params=GEVAL_TRANSCRIPT_PARAMS,
        verbose_mode=verbose,
        violation_types=spec.violation_types,
        outcome_labels=spec.outcome_labels,
    )


# ── Deterministic timing scores (E3) ──────────────────────────────────────────


@dataclass(frozen=True)
class DeterministicScore:
    name: str
    judge_score: int
    reason: str

    @property
    def score(self) -> float:
        return self.judge_score / JUDGE_SCORE_MAX

    @property
    def success(self) -> bool:
        return self.score >= 0.5


def _band_score(value: float, bands: tuple[tuple[float, int], ...], floor: int) -> int:
    for bound, score in bands:
        if value <= bound:
            return score
    return floor


def _aggregates(conversation: dict[str, Any]) -> dict[str, Any]:
    return conversation.get("derived_signals", {}).get("aggregates", {})


def score_response_latency(conversation: dict[str, Any]) -> DeterministicScore:
    agg = _aggregates(conversation)
    count = agg.get("latency_count", 0)
    if count == 0:
        return DeterministicScore(
            name="Response Latency",
            judge_score=JUDGE_SCORE_MAX,
            reason="No customer→bot response gaps to measure.",
        )
    p50 = agg["latency_p50_seconds"]
    p95 = agg["latency_p95_seconds"]
    worst = agg["latency_max_seconds"]
    base = _band_score(p50, LATENCY_P50_BANDS, LATENCY_FLOOR_SCORE)
    penalty = LATENCY_OUTLIER_PENALTY if worst > LATENCY_OUTLIER_SEC else 0
    reason = (
        f"Computed from word timestamps across {count} bot replies: "
        f"p50={p50:.2f}s, p95={p95:.2f}s, max={worst:.2f}s."
    )
    if penalty:
        reason += f" Penalty −{penalty}: slowest response exceeds {LATENCY_OUTLIER_SEC:.0f}s."
    return DeterministicScore(
        name="Response Latency",
        judge_score=max(JUDGE_SCORE_MIN, base - penalty),
        reason=reason,
    )


def score_dead_air(conversation: dict[str, Any]) -> DeterministicScore:
    agg = _aggregates(conversation)
    total = agg.get("dead_air_total_seconds", 0.0)
    events = agg.get("dead_air_event_count", 0)
    longest = agg.get("dead_air_max_seconds", 0.0)
    base = _band_score(total, DEAD_AIR_TOTAL_BANDS, DEAD_AIR_FLOOR_SCORE)
    penalty = DEAD_AIR_LONG_GAP_PENALTY if longest >= DEAD_AIR_LONG_GAP_SEC else 0
    reason = (
        f"Computed from word timestamps: {events} silence(s) ≥ 1.0s "
        f"(response gaps excluded), total {total:.1f}s, longest {longest:.1f}s."
    )
    if penalty:
        reason += f" Penalty −{penalty}: a single silence reaches {DEAD_AIR_LONG_GAP_SEC:.0f}s."
    return DeterministicScore(
        name="Dead Air",
        judge_score=max(JUDGE_SCORE_MIN, base - penalty),
        reason=reason,
    )


def score_interruptions(conversation: dict[str, Any]) -> DeterministicScore:
    agg = _aggregates(conversation)
    overlap = agg.get("interruption_overlap_total_seconds", 0.0)
    episodes = agg.get("interruption_episode_count", 0)
    failed_yields = agg.get("barge_in_failed_yield_count", 0)
    base = _band_score(overlap, OVERLAP_TOTAL_BANDS, OVERLAP_FLOOR_SCORE)
    penalty = min(failed_yields * FAILED_YIELD_PENALTY, FAILED_YIELD_PENALTY_MAX)
    reason = (
        f"Computed from word timestamps: {episodes} overlap episode(s), "
        f"total bot-over-customer overlap {overlap:.2f}s."
    )
    if penalty:
        reason += (
            f" Penalty −{penalty}: bot kept talking > {BARGE_IN_YIELD_OK_SEC:.0f}s "
            f"after {failed_yields} customer barge-in(s)."
        )
    return DeterministicScore(
        name="Interruptions",
        judge_score=max(JUDGE_SCORE_MIN, base - penalty),
        reason=reason,
    )


# ── Dimension registry ────────────────────────────────────────────────────────

# (dimension_key, metric_kind, metric, input_kind)
#   metric_kind "geval"        → VoiceGEval, input is the narrative LLMTestCase
#   metric_kind "deterministic"→ callable(conversation dict) → DeterministicScore
MetricEntry = tuple[str, str, Any, str]

DETERMINISTIC_SCORERS: dict[str, Callable[[dict[str, Any]], DeterministicScore]] = {
    "response_latency": score_response_latency,
    "dead_air": score_dead_air,
    "interruptions": score_interruptions,
}


def build_metrics(judge_model: LiteLLMModel, *, verbose: bool = True) -> list[MetricEntry]:
    def narrative(name: str, rubric_name: str, fallback: str) -> VoiceGEval:
        return _narrative_geval(
            name=name,
            rubric_name=rubric_name,
            fallback=fallback,
            judge_model=judge_model,
            verbose=verbose,
        )

    return [
        ("task_success", "geval", narrative("Task Success", "task_success", "Score whether the customer's call goal was achieved."), "llm"),
        ("conversation_quality", "geval", narrative("Conversation Quality", "conversation_quality", "Score flow, pacing, and naturalness."), "llm"),
        ("response_alignment", "geval", narrative("Response Alignment", "response_alignment", "Score whether bot responses addressed what the customer asked."), "llm"),
        ("user_disappointment", "geval", narrative("User Disappointment", "user_disappointment", "Score customer frustration from transcript content."), "llm"),
        ("conversation_progression", "geval", narrative("Conversation Progression", "conversation_progression", "Score whether the call moved forward without re-asking or repeating."), "llm"),
        ("faithfulness", "geval", narrative("Faithfulness", "faithfulness", "Score whether the bot stayed consistent and grounded in the call."), "llm"),
        ("sentiment_trajectory", "geval", narrative("Sentiment Trajectory", "sentiment_trajectory", "Score how customer sentiment evolved from start to end."), "llm"),
        ("call_outcome", "geval", narrative("Call Outcome", "call_outcome", "Classify how the call ended for the customer."), "llm"),
        ("response_latency", "deterministic", score_response_latency, "conversation"),
        ("dead_air", "deterministic", score_dead_air, "conversation"),
        ("interruptions", "deterministic", score_interruptions, "conversation"),
    ]
