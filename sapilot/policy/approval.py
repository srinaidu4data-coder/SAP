"""Human approval token flow for T2_SUPERVISED writes — portable + file-backed."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path

from sapilot.exceptions import ApprovalRequired, PolicyViolation
from sapilot.schemas import Tier


def _secret() -> bytes:
    env = os.environ.get("SAPILOT_APPROVAL_SECRET")
    if env:
        return env.encode("utf-8")
    # Stable per-machine lab secret file so tokens work cross-process
    root = Path(os.environ.get("SAPILOT_DATA", Path.cwd() / "data"))
    secret_path = root / "vault" / "approval.secret"
    secret_path.parent.mkdir(parents=True, exist_ok=True)
    if secret_path.exists():
        return secret_path.read_bytes().strip()
    raw = secrets.token_hex(32).encode("utf-8")
    secret_path.write_bytes(raw)
    try:
        os.chmod(secret_path, 0o600)
    except Exception:
        pass
    return raw


def _ledger_path() -> Path:
    root = Path(os.environ.get("SAPILOT_DATA", Path.cwd() / "data"))
    p = root / "vault" / "approvals.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


@dataclass
class ApprovalToken:
    token: str
    action_scope: str
    issued_at: float
    expires_at: float
    issuer: str = "human"

    def valid_for(self, action_scope: str, now: float | None = None) -> bool:
        ts = now if now is not None else time.time()
        if ts > self.expires_at:
            return False
        return self.action_scope == action_scope or self.action_scope == "*"


class ApprovalGate:
    """
    Issues and verifies short-lived approval tokens.

    Tokens are self-verifying (HMAC over scope|issued|expires|nonce) so they
    work across processes when SAPILOT_APPROVAL_SECRET (or vault secret file) matches.
    A JSONL ledger is append-only for SOX audit.
    """

    def __init__(self, secret: bytes | None = None, ttl_seconds: int = 900):
        self.secret = secret or _secret()
        self.ttl = ttl_seconds
        self._issued: dict[str, ApprovalToken] = {}

    def issue(self, action_scope: str, issuer: str = "human") -> ApprovalToken:
        nonce = secrets.token_hex(8)
        issued = time.time()
        expires = issued + self.ttl
        body = f"{action_scope}|{issued:.6f}|{expires:.6f}|{nonce}|{issuer}"
        body_b64 = base64.urlsafe_b64encode(body.encode("utf-8")).decode("ascii")
        sig = hmac.new(self.secret, body.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
        token = f"{body_b64}.{sig}"
        at = ApprovalToken(
            token=token,
            action_scope=action_scope,
            issued_at=issued,
            expires_at=expires,
            issuer=issuer,
        )
        self._issued[token] = at
        # Append-only ledger (cross-process evidence)
        rec = {
            "event": "issue",
            "token_fp": hashlib.sha256(token.encode()).hexdigest()[:16],
            **{k: v for k, v in asdict(at).items() if k != "token"},
            "token": token,
        }
        with open(_ledger_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
        return at

    def _parse_token(self, token: str) -> ApprovalToken | None:
        try:
            body_b64, sig = token.rsplit(".", 1)
            body = base64.urlsafe_b64decode(body_b64.encode("ascii")).decode("utf-8")
            expect = hmac.new(self.secret, body.encode("utf-8"), hashlib.sha256).hexdigest()[:32]
            if not hmac.compare_digest(expect, sig):
                return None
            parts = body.split("|")
            if len(parts) < 4:
                return None
            scope, issued_s, expires_s, nonce = parts[0], parts[1], parts[2], parts[3]
            issuer = parts[4] if len(parts) > 4 else "human"
            return ApprovalToken(
                token=token,
                action_scope=scope,
                issued_at=float(issued_s),
                expires_at=float(expires_s),
                issuer=issuer,
            )
        except Exception:
            return None

    def verify(self, token: str | None, action_scope: str) -> bool:
        if not token:
            return False
        # In-memory first
        at = self._issued.get(token)
        if at and at.valid_for(action_scope):
            return True
        # Self-verifying portable token
        parsed = self._parse_token(token)
        if parsed and parsed.valid_for(action_scope):
            self._issued[token] = parsed
            return True
        # Ledger fallback (same machine, secret rotated carefully)
        path = _ledger_path()
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if rec.get("token") == token:
                    at2 = ApprovalToken(
                        token=token,
                        action_scope=rec.get("action_scope", ""),
                        issued_at=float(rec.get("issued_at") or 0),
                        expires_at=float(rec.get("expires_at") or 0),
                        issuer=rec.get("issuer") or "human",
                    )
                    if at2.valid_for(action_scope):
                        # Still require HMAC if secret matches
                        if self._parse_token(token):
                            return True
        return False

    def require(
        self,
        tier: Tier,
        action_scope: str,
        token: str | None,
        *,
        capability_needs_approval: bool,
        confidence: float | None = None,
        min_confidence: float = 0.5,
    ) -> None:
        """
        Two independent gates, per shared-autonomy research (confidence alone
        is a poor detector of high-stakes/novel situations, and risk alone
        misses "the agent doesn't actually know where it's clicking"):

        1. Risk-classification gate: `capability_needs_approval` — driven by
           tier + the denylist's static scope list (F110 proposal, config
           commits, etc). Fires regardless of confidence. Unchanged.
        2. Confidence gate: if the caller supplies a grounding confidence
           (e.g. from confidence_from_samples on a vision-predicted click
           target) below `min_confidence`, treat it as needing approval too —
           even in T1_SANDBOX, which the risk gate alone never touches. A
           model that doesn't know where it's clicking shouldn't get to click
           just because the action itself is routine.
        """
        low_confidence = confidence is not None and confidence < min_confidence

        if tier == Tier.T3_OBSERVE:
            raise PolicyViolation(
                f"Action '{action_scope}' forbidden in T3_OBSERVE",
                tier=tier.value,
                action=action_scope,
            )
        if tier == Tier.T1_SANDBOX:
            if low_confidence and not self.verify(token, action_scope):
                raise ApprovalRequired(
                    f"Low grounding confidence ({confidence:.2f} < {min_confidence}) for "
                    f"'{action_scope}' — requires approval token even in T1_SANDBOX. "
                    f"Issue via: sapilot approve --scope {action_scope}"
                )
            return
        # T2
        if (capability_needs_approval or low_confidence) and not self.verify(token, action_scope):
            reason = (
                "T2_SUPERVISED requires approval token"
                if capability_needs_approval
                else f"low grounding confidence ({confidence:.2f} < {min_confidence})"
            )
            raise ApprovalRequired(
                f"{reason} for '{action_scope}'. Issue via: sapilot approve --scope {action_scope}"
            )
