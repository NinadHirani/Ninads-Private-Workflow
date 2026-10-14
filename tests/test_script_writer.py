"""Script writer logging hygiene: LLM API keys must never reach the log."""
import logging
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts import script_writer  # noqa: E402

FAKE_KEY = "AIzaFAKE" + "0123456789" * 5


def test_writer_failure_never_logs_api_key(monkeypatch, caplog):
    """A failed Gemini/Groq call must not leak the API key into the warning log."""
    monkeypatch.setenv("GEMINI_API_KEY", FAKE_KEY)
    monkeypatch.setenv("GROQ_API_KEY", FAKE_KEY)

    def boom(topic, category):
        raise RuntimeError(f"HTTP 403 from endpoint using key {FAKE_KEY}")

    monkeypatch.setattr(script_writer, "_try_gemini", boom)
    monkeypatch.setattr(script_writer, "_try_groq", boom)
    with caplog.at_level(logging.WARNING, logger="script_writer"):
        result = script_writer.write_script("quantum computing", category="anime")
    assert result["status"] == "SUCCESS"
    assert result["writer"] == "genre_template"
    assert FAKE_KEY not in caplog.text
    assert "[redacted]" in caplog.text
