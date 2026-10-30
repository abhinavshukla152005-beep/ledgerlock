"""Policy ingestion: structured YAML first, prose via the model second."""
from __future__ import annotations

from typing import Any

import yaml

from . import llm
from .engine import DEFAULT_RULES, normalize_rules


def load(text: str) -> tuple[dict[str, Any], str, str | None]:
    """Returns (rules, source, llm_source).

    source: 'inline-yaml' | 'vultr-inference' | 'defaults'
    """
    text = (text or "").strip()
    if not text:
        return dict(DEFAULT_RULES), "defaults", None

    try:
        parsed = yaml.safe_load(text)
    except yaml.YAMLError:
        parsed = None

    if isinstance(parsed, dict) and parsed:
        return normalize_rules(parsed), "inline-yaml", None

    extracted = llm.parse_policy(text)
    if extracted:
        return normalize_rules(extracted), "vultr-inference", "vultr-inference"

    return dict(DEFAULT_RULES), "defaults", None
