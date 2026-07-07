"""Judge LLM config — OpenAI, Anthropic, or Google only."""

from __future__ import annotations

import os
from dataclasses import dataclass

import litellm
from deepeval.models import LiteLLMModel
from litellm import get_llm_provider

SUPPORTED_PROVIDERS = frozenset({"openai", "anthropic", "gemini", "google"})

PROVIDER_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
}

JUDGE_MODEL_PRESETS: dict[str, tuple[str, ...]] = {
    "OpenAI": ("gpt-4o-mini", "gpt-4o"),
    "Anthropic": ("anthropic/claude-sonnet-4-6", "anthropic/claude-opus-4-8"),
    "Google": ("gemini/gemini-2.0-flash", "gemini/gemini-2.5-pro"),
}


@dataclass(frozen=True)
class JudgeConfig:
    model: str
    provider: str
    api_key: str


class VoiceBotJudgeModel(LiteLLMModel):
    def generate_raw_response(self, prompt: str, top_logprobs: int = 5):
        raise AttributeError("log_probs unsupported.")

    async def a_generate_raw_response(self, prompt: str, top_logprobs: int = 5):
        raise AttributeError("log_probs unsupported.")


def resolve_judge_config(model: str) -> JudgeConfig:
    model_id = model.strip()
    if not model_id:
        raise RuntimeError("Judge model is required.")

    try:
        _, provider, _, _ = get_llm_provider(model_id)
    except litellm.exceptions.BadRequestError as error:
        raise RuntimeError(f"Invalid judge model {model_id!r}: {error}") from error

    if provider not in SUPPORTED_PROVIDERS:
        raise RuntimeError(
            f"Judge provider {provider!r} is not supported. Use OpenAI, Anthropic, or Google."
        )

    key_env = PROVIDER_KEY_ENV[provider]
    api_key = (os.getenv(key_env) or "").strip()
    if not api_key:
        raise RuntimeError(f"{key_env} is required for judge model {model_id!r}.")

    return JudgeConfig(model=model_id, provider=provider, api_key=api_key)


def build_judge_model(*, model: str) -> VoiceBotJudgeModel:   #this return VoiceBotJudgeModel object which is a subclass of LiteLLMModel which is a wrapper around the LLM model
    cfg = resolve_judge_config(model)
    return VoiceBotJudgeModel(model=cfg.model, api_key=cfg.api_key)  #if want to use Azure API key , pass base_url too along with model and api_key.....also update SUPPORTED_PROVIDERS to include azure , PROVIDER_KEY_ENV to include azure_api_key etc.


def judge_model_label(judge: VoiceBotJudgeModel) -> str:
    return judge.get_model_name()
