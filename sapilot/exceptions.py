"""SAPILOT domain exceptions."""

from __future__ import annotations


class SapilotError(Exception):
    """Base error."""


class PreflightError(SapilotError):
    """Prerequisite check failed; start refused."""

    def __init__(self, checks: list[dict]):
        self.checks = checks
        failed = [c for c in checks if not c.get("ok")]
        lines = [f"[{c.get('id')}] {c.get('message')} — fix: {c.get('remediation')}" for c in failed]
        super().__init__("Preflight failed:\n" + "\n".join(lines))


class PolicyViolation(SapilotError):
    """Tier or denylist violation — terminates the run."""

    def __init__(self, reason: str, tier: str | None = None, action: str | None = None):
        self.reason = reason
        self.tier = tier
        self.action = action
        super().__init__(f"PolicyViolation(tier={tier}, action={action}): {reason}")


class GroundingError(SapilotError):
    """Action target not present in current screen snapshot."""


class RedactionError(SapilotError):
    """Payload failed redaction gate (fail closed)."""


class BudgetExceeded(SapilotError):
    """Governor budget exhausted."""


class LoopDetected(SapilotError):
    """State novelty check failed — agent is looping."""


class ConnectionError(SapilotError):
    """SAP connection failure."""


class CredentialsEnteredNoScripting(ConnectionError):
    """
    Username/password were typed into the SAP login window, but the
    server does not expose a scriptable session (sapgui/user_scripting).
    """

    def __init__(self, message: str, *, method: str = "keyboard"):
        super().__init__(message)
        self.method = method
        self.credentials_entered = True



class ApprovalRequired(SapilotError):
    """T2 write requires a human approval token."""
