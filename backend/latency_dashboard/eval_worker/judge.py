"""Judge LLM config — OpenAI, Anthropic, Google (API key), or Vertex AI via LiteLLM."""

from __future__ import annotations

import os
from dataclasses import dataclass

import litellm
from deepeval.models import LiteLLMModel
from litellm import get_llm_provider

SUPPORTED_PROVIDERS = frozenset({"openai", "anthropic", "gemini", "google", "vertex_ai"})

PROVIDER_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "google": "GEMINI_API_KEY",
}

# Vertex uses GCP ADC (GOOGLE_APPLICATION_CREDENTIALS) + project/location — no API key.
VERTEX_REQUIRED_ENV = (
    "VERTEXAI_PROJECT",
    "VERTEXAI_LOCATION",
    "GOOGLE_APPLICATION_CREDENTIALS",
)

JUDGE_MODEL_PRESETS: dict[str, tuple[str, ...]] = {
    "OpenAI": ("gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1"),
    "Anthropic": (
        "anthropic/claude-sonnet-4-6",
        "anthropic/claude-opus-4-8",
        "anthropic/claude-haiku-4-5-20251001",
    ),
    "Google": (
        "gemini/gemini-2.0-flash",
        "gemini/gemini-2.0-flash-lite",
        "gemini/gemini-2.5-flash",
        "gemini/gemini-2.5-flash-lite",
        "gemini/gemini-2.5-pro",
    ),
    "Vertex Gemini": (
        "vertex_ai/gemini-2.0-flash",
        "vertex_ai/gemini-2.0-flash-lite",
        "vertex_ai/gemini-2.5-flash",
        "vertex_ai/gemini-2.5-flash-lite",
        "vertex_ai/gemini-2.5-pro",
        "vertex_ai/gemini-3-flash-preview",
        "vertex_ai/gemini-3-pro-preview",
        "vertex_ai/gemini-3.1-flash-lite",
        "vertex_ai/gemini-3.1-pro-preview",
        "vertex_ai/gemini-3.5-flash",
    ),
    # Google Cloud / Anthropic Agent Platform IDs (Claude on Vertex).
    # https://platform.claude.com/docs/en/build-with-claude/claude-on-vertex-ai
    # Plus older Model Garden IDs still documented by Google Cloud / LiteLLM.
    "Vertex Claude": (
        "vertex_ai/claude-fable-5",
        "vertex_ai/claude-sonnet-5",
        "vertex_ai/claude-opus-4-8",
        "vertex_ai/claude-opus-4-7",
        "vertex_ai/claude-opus-4-6",
        "vertex_ai/claude-sonnet-4-6",
        "vertex_ai/claude-sonnet-4-5@20250929",
        "vertex_ai/claude-opus-4-5@20251101",
        "vertex_ai/claude-haiku-4-5@20251001",
        "vertex_ai/claude-sonnet-4@20250514",
        "vertex_ai/claude-opus-4-1@20250805",
        "vertex_ai/claude-opus-4@20250514",
        "vertex_ai/claude-3-5-haiku@20241022",
        "vertex_ai/claude-3-7-sonnet@20250219",
        "vertex_ai/claude-3-5-sonnet-v2@20241022",
        "vertex_ai/claude-3-5-sonnet@20240620",
        "vertex_ai/claude-3-opus@20240229",
        "vertex_ai/claude-3-sonnet@20240229",
        "vertex_ai/claude-3-haiku@20240307",
    ),
}


@dataclass(frozen=True)
class JudgeConfig:
    model: str
    provider: str
    api_key: str | None = None


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
            f"Judge provider {provider!r} is not supported. "
            "Use OpenAI, Anthropic, Google, or Vertex AI (vertex_ai/...)."
        )

    if provider == "vertex_ai":
        missing = [name for name in VERTEX_REQUIRED_ENV if not (os.getenv(name) or "").strip()]
        if missing:
            raise RuntimeError(
                f"{', '.join(missing)} required for Vertex judge model {model_id!r}."
            )
        return JudgeConfig(model=model_id, provider=provider, api_key=None)

    key_env = PROVIDER_KEY_ENV[provider]
    api_key = (os.getenv(key_env) or "").strip()
    if not api_key:
        raise RuntimeError(f"{key_env} is required for judge model {model_id!r}.")

    return JudgeConfig(model=model_id, provider=provider, api_key=api_key)


def build_judge_model(*, model: str) -> VoiceBotJudgeModel:
    cfg = resolve_judge_config(model)
    if cfg.provider == "vertex_ai":
        # LiteLLM reads VERTEXAI_PROJECT / VERTEXAI_LOCATION / GOOGLE_APPLICATION_CREDENTIALS.
        return VoiceBotJudgeModel(model=cfg.model)
    return VoiceBotJudgeModel(model=cfg.model, api_key=cfg.api_key)


def judge_model_label(judge: VoiceBotJudgeModel) -> str:
    return judge.get_model_name()
