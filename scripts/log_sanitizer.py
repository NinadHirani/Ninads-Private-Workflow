"""Central log redaction for AI Shorts Factory.

No credential value, token, or session material should ever reach a log line.
Every module routes raw exception text through redact() before logging it.
"""
import os
import re

# Long opaque runs of token-ish characters are usually session tokens, cookies
# or signed payloads that APIs occasionally echo inside error messages.
_LONG_TOKEN_LIKE_RUN = re.compile(r"[A-Za-z0-9+/=_-]{40,}")

# Names redacted even when they do not match the generic suffix rule.
_EXPLICIT_SECRET_VARS = ("IG_USERNAME", "IG_PASSWORD")
_SECRET_SUFFIXES = ("_TOKEN", "_SECRET", "_PASSWORD", "_API_KEY", "_APIKEY", "_KEY")


def _secret_values() -> list:
    """Candidate secret values currently in the environment (deduplicated)."""
    names = list(_EXPLICIT_SECRET_VARS)
    for key in os.environ:
        if key.upper().endswith(_SECRET_SUFFIXES):
            names.append(key)
    values = []
    for name in names:
        value = (os.getenv(name) or "").strip()
        if len(value) >= 4 and value not in values:
            values.append(value)
    return values


def redact(text: str) -> str:
    """Replace credential values and token-like runs with [redacted] placeholders."""
    for value in _secret_values():
        text = text.replace(value, "[redacted]")
    return _LONG_TOKEN_LIKE_RUN.sub("[redacted-token]", text)
