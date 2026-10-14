"""Central log redaction: no credentials or token-like data may reach a log line."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts.log_sanitizer import redact  # noqa: E402


def test_redacts_ig_password_and_username(monkeypatch):
    monkeypatch.setenv("IG_PASSWORD", "supersecretpw")
    monkeypatch.setenv("IG_USERNAME", "myhandle")
    out = redact("login failed for myhandle: password supersecretpw rejected")
    assert "supersecretpw" not in out
    assert "myhandle" not in out
    assert "[redacted]" in out


def test_redacts_generic_secret_env_vars(monkeypatch):
    monkeypatch.setenv("YOUTUBE_REFRESH_TOKEN", "1//0abcDEFrefreshTOKEN")
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestKey1234567890")
    out = redact("bad request token 1//0abcDEFrefreshTOKEN with key AIzaSyTestKey1234567890")
    assert "1//0abcDEFrefreshTOKEN" not in out
    assert "AIzaSyTestKey1234567890" not in out


def test_redacts_long_token_like_runs():
    token = "x" * 60
    out = redact(f"session cookie {token} expired")
    assert token not in out
    assert "[redacted-token]" in out


def test_leaves_normal_text_alone():
    text = "quota exceeded after 3 uploads today"
    assert redact(text) == text
