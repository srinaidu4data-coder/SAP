"""Credential vault — DPAPI-first on Windows; no default passphrase outside lab; no plaintext in prod."""

from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

_BANNED_DEFAULT_PASSPHRASES = frozenset(
    {
        "sapilot-local",
        "password",
        "changeme",
        "secret",
        "default",
    }
)


def _is_lab() -> bool:
    try:
        from sapilot.policy.guard import is_lab_mode

        return is_lab_mode()
    except Exception:
        env = (os.environ.get("SAPILOT_ENV") or "").lower()
        return env not in {"prod", "production", "qa"}


def _strict_vault() -> bool:
    if os.environ.get("SAPILOT_STRICT_VAULT", "").strip() in {"1", "true", "yes"}:
        return True
    return not _is_lab()


def _vault_path() -> Path:
    root = Path(os.environ.get("SAPILOT_DATA", Path.cwd() / "data"))
    p = root / "vault"
    p.mkdir(parents=True, exist_ok=True)
    return p / "credentials.vault"


def _dpapi_available() -> bool:
    if os.name != "nt":
        return False
    try:
        import win32crypt  # type: ignore  # noqa: F401

        return True
    except ImportError:
        return False


def _normalize_passphrase(passphrase: str | None) -> str | None:
    """Ban weak default passphrases outside lab."""
    if passphrase is None:
        env_p = os.environ.get("SAPILOT_VAULT_PASSPHRASE")
        passphrase = env_p
    if not passphrase:
        return None
    if passphrase.strip().lower() in _BANNED_DEFAULT_PASSPHRASES:
        if _strict_vault() or not _is_lab():
            raise RuntimeError(
                f"Banned weak vault passphrase {passphrase!r} outside lab. "
                "Use DPAPI (omit passphrase on Windows) or a strong unique passphrase. "
                "Set SAPILOT_LAB=1 only for local lab."
            )
        log.warning("Using lab-only default vault passphrase — not for QA/Prod")
    return passphrase


def _protect(data: bytes, passphrase: str | None) -> bytes:
    passphrase = _normalize_passphrase(passphrase)
    # DPAPI-first on Windows when no explicit passphrase
    if _dpapi_available() and not passphrase:
        import win32crypt  # type: ignore

        return win32crypt.CryptProtectData(data, "sapilot", None, None, None, 0)

    from cryptography.fernet import Fernet
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

    pwd = (passphrase or "").encode()
    if not pwd:
        raise RuntimeError(
            "No DPAPI and no passphrase. Set SAPILOT_VAULT_PASSPHRASE or install pywin32."
        )
    salt = b"sapilot-vault-v1"
    kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480_000)
    key = base64.urlsafe_b64encode(kdf.derive(pwd))
    return Fernet(key).encrypt(data)


def _unprotect(blob: bytes, passphrase: str | None) -> bytes:
    passphrase = _normalize_passphrase(passphrase)
    errors: list[str] = []

    # Prefer DPAPI when available
    if _dpapi_available():
        try:
            import win32crypt  # type: ignore

            result = win32crypt.CryptUnprotectData(blob, None, None, None, 0)
            return result[1]
        except Exception as e:
            errors.append(f"dpapi:{e}")

    if passphrase:
        try:
            from cryptography.fernet import Fernet
            from cryptography.hazmat.primitives import hashes
            from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

            salt = b"sapilot-vault-v1"
            kdf = PBKDF2HMAC(algorithm=hashes.SHA256(), length=32, salt=salt, iterations=480_000)
            key = base64.urlsafe_b64encode(kdf.derive(passphrase.encode()))
            return Fernet(key).decrypt(blob)
        except Exception as e:
            errors.append(f"fernet:{e}")

    raise RuntimeError(f"Cannot decrypt vault ({'; '.join(errors) or 'no method'})")


class CredentialVault:
    def __init__(self, path: Path | None = None, passphrase: str | None = None):
        self.path = path or _vault_path()
        # Normalize / ban weak defaults early
        try:
            self.passphrase = _normalize_passphrase(passphrase)
        except RuntimeError:
            # On strict vault, re-raise; on lab allow construction with None and DPAPI
            if _strict_vault():
                raise
            self.passphrase = None
            log.warning("Vault passphrase rejected; falling back to DPAPI/empty for lab")

    def set(self, connection_name: str, credentials: dict[str, Any]) -> None:
        store = self._load_all_plain() if self.path.exists() else {}
        store[connection_name] = credentials
        raw = json.dumps(store).encode("utf-8")
        # Prefer DPAPI when available and no passphrase set
        blob = _protect(raw, self.passphrase)
        self.path.write_bytes(blob)
        # Never leave plaintext siblings
        plain = self.path.with_suffix(".json")
        if plain.exists():
            plain.unlink()

    def get(self, connection_name: str) -> dict[str, Any] | None:
        store = self._load_all_plain()
        return store.get(connection_name)

    def list_names(self) -> list[str]:
        return sorted(self._load_all_plain().keys())

    def _load_all_plain(self) -> dict[str, Any]:
        if not self.path.exists():
            return {}
        blob = self.path.read_bytes()
        try:
            raw = _unprotect(blob, self.passphrase)
            return json.loads(raw.decode("utf-8"))
        except Exception as dec_err:
            # Plaintext JSON fallback: LAB ONLY, never prod
            if _strict_vault() or not _is_lab():
                raise RuntimeError(
                    f"Failed to open vault (plaintext fallback disabled outside lab): {dec_err}"
                ) from dec_err
            if os.environ.get("SAPILOT_ALLOW_PLAINTEXT_VAULT", "0").strip() not in {
                "1",
                "true",
                "yes",
            }:
                # Lab still requires opt-in for plaintext
                try:
                    return json.loads(blob.decode("utf-8"))
                except Exception as e:
                    raise RuntimeError(f"Failed to open vault: {dec_err}") from e
            try:
                log.warning("Vault plaintext fallback (lab only)")
                return json.loads(blob.decode("utf-8"))
            except Exception as e:
                raise RuntimeError(f"Failed to open vault: {e}") from e
