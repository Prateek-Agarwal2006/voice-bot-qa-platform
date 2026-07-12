"""Voice QA prompts on DeepEval GEval — measure/score logic unchanged."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List, Optional, Tuple, Union

import jinja2
from deepeval.errors import MissingTestCaseParamsError
from deepeval.metrics import GEval
from deepeval.metrics.base_metric import MetricTemplateMethod
from deepeval.metrics.g_eval.utils import (
    calculate_weighted_summed_score,
    format_rubrics,
    no_log_prob_support,
    number_evaluation_steps,
)
from deepeval.metrics.utils import (
    accrue_token_usage,
    a_generate_with_schema_and_extract,
    generate_with_schema_and_extract,
    trimAndLoadJson,
)
from deepeval.test_case import LLMTestCase
from pydantic import BaseModel, Field

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts" / "geval"
_VOICE_PROMPTS = frozenset({"generate_evaluation_steps", "generate_evaluation_results"})


class ViolationModel(BaseModel):
    type: str
    turn_index: Optional[int] = None
    quote: Optional[str] = None


class VoiceJudgeVerdict(BaseModel):
    """Judge output: raw 0-10 score (base GEval normalises), reason, evidence, optional outcome label."""

    reason: str
    score: float
    violations: List[ViolationModel] = Field(default_factory=list)
    outcome: Optional[str] = None


class VoiceGEval(GEval):
    """GEval with voice-call QA judge prompts (DeepEval measure/score logic unchanged)."""

    def __init__(
        self,
        *args: Any,
        violation_types: Optional[list[dict[str, str]]] = None,
        outcome_labels: Optional[list[dict[str, str]]] = None,
        **kwargs: Any,
    ) -> None:
        self.violation_types = violation_types or []
        self.outcome_labels = outcome_labels or []
        self.violations: list[dict[str, Any]] = []
        self.outcome: Optional[str] = None
        super().__init__(*args, **kwargs)

    def _record_verdict_extras(self, violations: Any, outcome: Any) -> None:
        cleaned: list[dict[str, Any]] = []
        for item in violations or []:
            if isinstance(item, ViolationModel):
                cleaned.append(item.model_dump())
            elif isinstance(item, dict) and item.get("type"):
                cleaned.append({
                    "type": item.get("type"),
                    "turn_index": item.get("turn_index"),
                    "quote": item.get("quote"),
                })
        self.violations = cleaned
        self.outcome = outcome if isinstance(outcome, str) and outcome.strip() else None

    def _extract_verdict_schema(self, verdict: VoiceJudgeVerdict) -> Tuple[Union[int, float], str]:
        self._record_verdict_extras(verdict.violations, verdict.outcome)
        return verdict.score, verdict.reason

    def _extract_verdict_json(self, data: dict) -> Tuple[Union[int, float], str]:
        self._record_verdict_extras(data.get("violations"), data.get("outcome"))
        return data["score"], data["reason"]

    def _get_prompt(
        self,
        method: MetricTemplateMethod,
        *,
        template_class: Optional[str] = None,
        multimodal: bool = False,
        strict: bool = True,
        **kwargs: Any,
    ) -> str:
        if method not in _VOICE_PROMPTS:
            return super()._get_prompt(
                method,
                template_class=template_class,
                multimodal=multimodal,
                strict=strict,
                **kwargs,
            )
        path = PROMPTS_DIR / f"{method}.txt"
        template = jinja2.Environment().from_string(path.read_text(encoding="utf-8"))
        return template.render(**kwargs)

    def _conversation_block(self, test_case: LLMTestCase) -> str:
        content = test_case.actual_output
        if content is None or (isinstance(content, str) and not content.strip()):
            error_str = f"'actual_output' cannot be empty for the '{self.__name__}' metric"
            self.error = error_str
            raise MissingTestCaseParamsError(error_str)
        return content if isinstance(content, str) else str(content)

    def _results_prompt(
        self,
        test_case: LLMTestCase,
        *,
        multimodal: bool,
        _additional_context: Optional[str],
    ) -> str:
        if self.strict_mode:
            return super()._get_prompt(
                "generate_strict_evaluation_results",
                evaluation_steps=number_evaluation_steps(self.evaluation_steps),
                test_case_content=self._conversation_block(test_case),
                parameters="",
                _additional_context=_additional_context,
                multimodal=multimodal,
            )
        rubric_str = format_rubrics(self.rubric) if self.rubric else None
        return self._get_prompt(
            "generate_evaluation_results",
            evaluation_steps=number_evaluation_steps(self.evaluation_steps),
            conversation=self._conversation_block(test_case),
            rubric=rubric_str,
            score_range=self.score_range,
            violation_types=self.violation_types,
            outcome_labels=self.outcome_labels,
            _additional_context=_additional_context,
            multimodal=multimodal,
        )

    async def _a_evaluate(
        self,
        test_case: LLMTestCase,
        multimodal: bool,
        _additional_context: Optional[str] = None,
    ) -> Tuple[Union[int, float], str]:
        prompt = self._results_prompt(
            test_case, multimodal=multimodal, _additional_context=_additional_context
        )
        try:
            if no_log_prob_support(self.model):
                raise AttributeError("log_probs unsupported.")
            res, cost = await self.model.a_generate_raw_response(prompt, top_logprobs=self.top_logprobs)
            self._accrue_cost(cost)
            accrue_token_usage(self, cost)
            data = trimAndLoadJson(res.choices[0].message.content, self)
            self._record_verdict_extras(data.get("violations"), data.get("outcome"))
            reason = data["reason"]
            score = data["score"]
            if self.strict_mode:
                return score, reason
            try:
                return calculate_weighted_summed_score(score, res), reason
            except (KeyError, AttributeError, TypeError, ValueError):
                return score, reason
        except AttributeError:
            return await a_generate_with_schema_and_extract(
                metric=self,
                prompt=prompt,
                schema_cls=VoiceJudgeVerdict,
                extract_schema=self._extract_verdict_schema,
                extract_json=self._extract_verdict_json,
            )

    def _evaluate(
        self,
        test_case: LLMTestCase,
        multimodal: bool,
        _additional_context: Optional[str] = None,
    ) -> Tuple[Union[int, float], str]:
        prompt = self._results_prompt(
            test_case, multimodal=multimodal, _additional_context=_additional_context
        )
        try:
            if no_log_prob_support(self.model):
                raise AttributeError("log_probs unsupported.")
            res, cost = self.model.generate_raw_response(prompt, top_logprobs=self.top_logprobs)
            self._accrue_cost(cost)
            accrue_token_usage(self, cost)
            data = trimAndLoadJson(res.choices[0].message.content, self)
            self._record_verdict_extras(data.get("violations"), data.get("outcome"))
            reason = data["reason"]
            score = data["score"]
            if self.strict_mode:
                return score, reason
            try:
                return calculate_weighted_summed_score(score, res), reason
            except (KeyError, AttributeError, TypeError, ValueError):
                return score, reason
        except AttributeError:
            return generate_with_schema_and_extract(
                metric=self,
                prompt=prompt,
                schema_cls=VoiceJudgeVerdict,
                extract_schema=self._extract_verdict_schema,
                extract_json=self._extract_verdict_json,
            )
