"""Multi-model router — SpaceXAI primary; optional second-vendor critic."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import time
from enum import Enum
from typing import Any

from sapilot.security.redaction import RedactionGate

log = logging.getLogger(__name__)


class Role(str, Enum):
    SCREEN_UNDERSTANDING = "SCREEN_UNDERSTANDING"
    PLANNING = "PLANNING"
    CRITIC = "CRITIC"
    ERROR_DIAGNOSIS = "ERROR_DIAGNOSIS"


class ModelRouter:
    """
    OpenAI-compatible chat router.

    Key resolution (first non-empty wins for default path):
      OPENAI_API_KEY → api.openai.com (or OPENAI_BASE_URL)
      XAI_API_KEY     → api.x.ai (SpaceXAI)

    Models via SAPILOT_PLANNER_MODEL / CRITIC / DIAGNOSIS / SCREEN_MODEL.
    Every call logged with prompt hash, model, latency, tokens.
    """

    def __init__(self, redaction: RedactionGate | None = None):
        self.redaction = redaction or RedactionGate()
        self.call_log: list[dict[str, Any]] = []
        self.openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
        self.openai_base = os.environ.get(
            "OPENAI_BASE_URL", "https://api.openai.com/v1"
        ).strip()
        self.xai_key = os.environ.get("XAI_API_KEY", "").strip()
        self.xai_base = os.environ.get("XAI_BASE_URL", "https://api.x.ai/v1").strip()
        self.anthropic_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()

        # Prefer OpenAI models when OPENAI key present; else xAI defaults
        if self.openai_key:
            default_model = os.environ.get("SAPILOT_PLANNER_MODEL", "gpt-4o")
        else:
            default_model = os.environ.get("SAPILOT_PLANNER_MODEL", "grok-4.5")
        self.planner_model = os.environ.get("SAPILOT_PLANNER_MODEL", default_model)
        self.critic_model = os.environ.get("SAPILOT_CRITIC_MODEL", default_model)
        self.diagnosis_model = os.environ.get("SAPILOT_DIAGNOSIS_MODEL", default_model)
        self.screen_model = os.environ.get(
            "SAPILOT_SCREEN_MODEL",
            "gpt-4o-mini" if self.openai_key else self.planner_model,
        )

    def complete(
        self,
        role: Role,
        system: str,
        user: str,
        *,
        temperature: float = 0.2,
        json_mode: bool = True,
    ) -> str:
        safe_system = self.redaction.redact_text(system)
        safe_user = self.redaction.redact_text(user)
        model = self._model_for(role)
        prompt_hash = hashlib.sha256(f"{safe_system}\n{safe_user}".encode()).hexdigest()[:16]
        t0 = time.monotonic()
        text, tokens = self._call(model, safe_system, safe_user, temperature, json_mode, role)
        latency_ms = int((time.monotonic() - t0) * 1000)
        self.call_log.append(
            {
                "role": role.value,
                "model": model,
                "prompt_hash": prompt_hash,
                "latency_ms": latency_ms,
                "tokens": tokens,
            }
        )
        return text

    def _model_for(self, role: Role) -> str:
        return {
            Role.SCREEN_UNDERSTANDING: self.screen_model,
            Role.PLANNING: self.planner_model,
            Role.CRITIC: self.critic_model,
            Role.ERROR_DIAGNOSIS: self.diagnosis_model,
        }[role]

    def _call(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float,
        json_mode: bool,
        role: Role,
    ) -> tuple[str, int]:
        # Offline / no key: deterministic stub for tests
        if not self.openai_key and not self.xai_key and not self.anthropic_key:
            return self._stub(role, user), 0

        if role == Role.CRITIC and self.anthropic_key and model.startswith("claude"):
            return self._call_anthropic(model, system, user, temperature)

        # Prefer OpenAI when key is set (unless model is clearly xAI/grok and XAI key exists)
        use_xai = bool(self.xai_key) and (
            model.startswith("grok") or (not self.openai_key)
        )
        if use_xai:
            return self._call_openai_compat(
                self.xai_key, self.xai_base, model, system, user, temperature, json_mode
            )
        if self.openai_key:
            return self._call_openai_compat(
                self.openai_key,
                self.openai_base,
                model,
                system,
                user,
                temperature,
                json_mode,
            )
        if self.xai_key:
            return self._call_openai_compat(
                self.xai_key, self.xai_base, model, system, user, temperature, json_mode
            )
        return self._stub(role, user), 0

    def _call_openai_compat(
        self,
        api_key: str,
        base_url: str,
        model: str,
        system: str,
        user: str,
        temperature: float,
        json_mode: bool,
    ) -> tuple[str, int]:
        from openai import OpenAI

        client = OpenAI(api_key=api_key, base_url=base_url)
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = client.chat.completions.create(**kwargs)
        text = resp.choices[0].message.content or ""
        tokens = int(getattr(resp.usage, "total_tokens", 0) or 0)
        return text, tokens

    def _call_anthropic(
        self,
        model: str,
        system: str,
        user: str,
        temperature: float,
    ) -> tuple[str, int]:
        import requests

        resp = requests.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": self.anthropic_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json={
                "model": model,
                "max_tokens": 4096,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        text = "".join(
            b.get("text", "") for b in data.get("content", []) if b.get("type") == "text"
        )
        tokens = int(data.get("usage", {}).get("input_tokens", 0)) + int(
            data.get("usage", {}).get("output_tokens", 0)
        )
        return text, tokens

    def _stub(self, role: Role, user: str) -> str:
        if role == Role.CRITIC:
            return json.dumps({"verdict": "APPROVE", "reasons": ["stub critic"]})
        if role == Role.PLANNING:
            return json.dumps(
                {
                    "assessment": "Stub planner — no API key; escalate for human.",
                    "gap": "Live model not configured",
                    "action": {
                        "type": "escalate",
                        "target": "",
                        "value": "Set XAI_API_KEY for autonomous planning",
                        "expect": "human takes over",
                    },
                    "justification_ref": "stub:no_api_key",
                    "confidence": 1.0,
                }
            )
        return json.dumps({"note": "stub", "role": role.value})
