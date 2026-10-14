"""auto_run Gemini topic generation: the API key must never sit in a URL or a log line."""
import os
import sys
import urllib.error

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts import auto_run  # noqa: E402
from scripts.log_sanitizer import redact  # noqa: E402


def test_gemini_url_carries_key_in_header_not_query():
    url, headers = auto_run._gemini_url_and_headers("AIzaSyTestKey1234567890")
    assert "key=" not in url
    assert headers["x-goog-api-key"] == "AIzaSyTestKey1234567890"


def test_gemini_key_value_redacted_from_error_text(monkeypatch):
    """Whatever Google echoes back (str or the request URL), the key must not survive redaction."""
    monkeypatch.setenv("GEMINI_API_KEY", "AIzaSyTestKey1234567890")
    err = urllib.error.HTTPError(
        "https://generativelanguage.googleapis.com/v1beta/models/"
        "gemini-2.0-flash:generateContent?key=AIzaSyTestKey1234567890",
        400, "Bad Request", None, None)
    assert "AIzaSyTestKey1234567890" not in redact(str(err))
    assert "AIzaSyTestKey1234567890" not in redact(err.url)


def test_generate_ai_topics_returns_empty_without_key(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert auto_run.generate_ai_topics("quantum computing") == []
