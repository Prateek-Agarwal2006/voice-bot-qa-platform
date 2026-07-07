from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from deepeval.models import LiteLLMModel
from deepeval.test_case import SingleTurnParams

from latency_dashboard.eval_worker.voice_geval import VoiceGEval

# rubrics/ lives at backend/rubrics/ — two levels up from eval_worker/
RUBRICS_DIR = Path(__file__).resolve().parent.parent.parent / "rubrics"

TestCaseKind = Literal["llm", "llm_timing"]

GEVAL_TRANSCRIPT_PARAMS = [SingleTurnParams.ACTUAL_OUTPUT]

TRANSCRIPT_HINT = (
    " The Conversation is the full ElevenLabs Scribe transcript (Customer ↔ Voice Bot). "
    "Score the entire call holistically — not isolated lines."
)

TIMING_TRANSCRIPT_HINT = (
    " The Conversation includes per-word timestamps and derived_signals hints. "
    "Score holistically across the full call — verify gaps and overlap from word times, "
    "not from turn count or ASR turn splits after barge-in. derived_signals are hints only."
)


def load_rubric(name: str, *, fallback: str) -> str:
    path = RUBRICS_DIR / f"{name}.md"
    if path.exists():
        return path.read_text(encoding="utf-8").strip()
    return fallback


def _narrative_geval(*, name: str, rubric_name: str, fallback: str, judge_model: LiteLLMModel, verbose: bool) -> VoiceGEval:
    return VoiceGEval(
        name=name,
        criteria=load_rubric(rubric_name, fallback=fallback) + TRANSCRIPT_HINT,
        model=judge_model,
        evaluation_params=GEVAL_TRANSCRIPT_PARAMS,
        verbose_mode=verbose,
    )


def _timing_geval(*, name: str, rubric_name: str, fallback: str, judge_model: LiteLLMModel, verbose: bool) -> VoiceGEval:
    return VoiceGEval(
        name=name,
        criteria=load_rubric(rubric_name, fallback=fallback) + TIMING_TRANSCRIPT_HINT,
        model=judge_model,
        evaluation_params=GEVAL_TRANSCRIPT_PARAMS,
        verbose_mode=verbose,
    )


def build_metrics(judge_model: LiteLLMModel, *, verbose: bool = True) -> list[tuple[str, str, Any, TestCaseKind]]:
    return [
        ("task_success", "geval", _narrative_geval(name="Task Success", rubric_name="task_success", fallback="Score whether the customer's call goal was achieved.", judge_model=judge_model, verbose=verbose), "llm"),
        ("conversation_quality", "geval", _narrative_geval(name="Conversation Quality", rubric_name="conversation_quality", fallback="Score flow, pacing, and naturalness.", judge_model=judge_model, verbose=verbose), "llm"),
        ("response_alignment", "geval", _narrative_geval(name="Response Alignment", rubric_name="response_alignment", fallback="Score whether bot responses addressed what the customer asked.", judge_model=judge_model, verbose=verbose), "llm"),
        ("user_disappointment", "geval", _narrative_geval(name="User Disappointment", rubric_name="user_disappointment", fallback="Score customer frustration from transcript content.", judge_model=judge_model, verbose=verbose), "llm"),
        ("response_latency", "geval", _timing_geval(name="Response Latency", rubric_name="response_latency", fallback="Score bot response latency from per-word timestamps.", judge_model=judge_model, verbose=verbose), "llm_timing"),
        ("dead_air", "geval", _timing_geval(name="Dead Air", rubric_name="dead_air", fallback="Score dead air from per-word timestamps.", judge_model=judge_model, verbose=verbose), "llm_timing"),
        ("interruptions", "geval", _timing_geval(name="Interruptions", rubric_name="interruptions", fallback="Score interruptions from per-word timestamps.", judge_model=judge_model, verbose=verbose), "llm_timing"),
    ]
