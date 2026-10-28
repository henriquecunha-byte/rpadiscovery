"""Server-side AI routing. Provider choice never falls back to another account."""
from __future__ import annotations

from dataclasses import dataclass, field
import os

from openai import OpenAI

from .errors import PublicProcessingError


LOVABLE_BASE_URL = "https://ai.gateway.lovable.dev/v1"
OPENAI_BASE_URL = "https://api.openai.com/v1"


@dataclass(frozen=True)
class AISettings:
    provider: str
    model: str
    api_key: str = field(repr=False)


def settings() -> AISettings:
    # A legacy OPENAI_API_KEY in .env must not opt the app into direct billing.
    provider = os.getenv("AI_PROVIDER", "lovable").strip().lower()
    if provider == "lovable":
        return AISettings(provider, os.getenv("LOVABLE_MODEL", "").strip() or "openai/gpt-5.6-luna",
                          os.getenv("LOVABLE_API_KEY", "").strip())
    if provider == "openai":
        return AISettings(provider, os.getenv("OPENAI_MODEL", "").strip() or "gpt-5.6-luna",
                          os.getenv("OPENAI_API_KEY", "").strip())
    raise PublicProcessingError("ai_configuration")


def is_configured() -> bool:
    """Presence check only; does not claim the credential was verified remotely."""
    try:
        return bool(settings().api_key)
    except PublicProcessingError:
        return False


def model_name() -> str:
    return settings().model


def create_client() -> OpenAI:
    config = settings()
    if not config.api_key:
        raise PublicProcessingError("ai_configuration")
    options = dict(api_key=config.api_key, timeout=120.0, max_retries=0)
    if config.provider == "lovable":
        # Explicit URL/identity prevent legacy OpenAI environment variables from
        # redirecting the project key or attaching another account's metadata.
        options.update(base_url=LOVABLE_BASE_URL, organization="", project="",
                       default_headers={"Lovable-API-Key": config.api_key})
    else:
        options["base_url"] = OPENAI_BASE_URL
    return OpenAI(**options)
