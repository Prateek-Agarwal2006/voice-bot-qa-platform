"""Voice QA prompts on DeepEval GEval — measure/score logic unchanged."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Tuple, Union

import jinja2
from deepeval.errors import MissingTestCaseParamsError
from deepeval.metrics import GEval
from deepeval.metrics.base_metric import MetricTemplateMethod
from deepeval.metrics.g_eval import schema as gschema
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

PROMPTS_DIR = Path(__file__).resolve().parent / "prompts" / "geval"
_VOICE_PROMPTS = frozenset({"generate_evaluation_steps", "generate_evaluation_results"})


class VoiceGEval(GEval):
    """GEval with voice-call QA judge prompts (DeepEval measure/score logic unchanged)."""

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
                schema_cls=gschema.ReasonScore,
                extract_schema=lambda s: (s.score, s.reason),
                extract_json=lambda d: (d["score"], d["reason"]),
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
                schema_cls=gschema.ReasonScore,
                extract_schema=lambda s: (s.score, s.reason),
                extract_json=lambda d: (d["score"], d["reason"]),
            )
