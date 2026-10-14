"""Guard: every raw exception that reaches a log line must go through redact().

scripts/log_sanitizer.py states the invariant: "Every module routes raw
exception text through redact() before logging it." PRs #6 and #7 fixed several
modules; this test proves no module was missed, and that the redaction actually
hides a credential value that an exception carried.
"""
import bisect
import logging
import pathlib
import re

import pytest

SCRIPTS_DIR = pathlib.Path(__file__).resolve().parent.parent / "scripts"
BARE_ARG = re.compile(r"^(?:e|exc|err|ex)$")
LITERALS = {"str(e)", "str(exc)", "str(err)", "str(ex)"}
_LEVELS = r"(?:debug|info|warning|error|exception|critical)"


def _logger_statements(src: str):
    """Yield (start_offset, statement) for every logger.<level>(...) call."""
    for m in re.finditer(r"logger\.%s\s*\(" % _LEVELS, src):
        i = m.end()
        depth = 1
        while i < len(src) and depth:
            c = src[i]
            if c == "(":
                depth += 1
            elif c == ")":
                depth -= 1
            i += 1
        yield m.start(), src[m.start():i]


def _top_level_args(stmt: str):
    inner = stmt[stmt.index("(") + 1:-1]
    parts, depth, cur = [], 0, []
    for ch in inner:
        if ch in "([{":
            depth += 1
        elif ch in ")]}" ":
            depth -= 1
        if ch == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def test_every_logged_exception_is_redacted():
    offenders = []
    for path in sorted(SCRIPTS_DIR.glob("*.py")):
        src = path.read_text(encoding="utf-8")
        line_starts = [0] + [m.end() for m in re.finditer(r"\n", src)]
        for start, stmt in _logger_statements(src):
            line_no = bisect.bisect_right(line_starts, start)
            for arg in _top_level_args(stmt):
                a = arg.strip()
                if BARE_ARG.match(a) or a in LITERALS:
                    offenders.append("%s:%d: %s" % (path.name, line_no, " ".join(stmt.split())[:100]))
    assert not offenders, (
        "Raw exception text reaches a log line; route it through redact():\n"
        + "\n".join(offenders)
    )


def test_voiceover_failure_logs_redacted(caplog, monkeypatch, tmp_path):
    import scripts.voiceover as vo

    monkeypatch.setenv("EDGE_TTS_TEST_SECRET_TOKEN", "supersecretvalue99")
    monkeypatch.setattr(vo, "VOICES_FALLBACK", ["test-voice"])
    monkeypatch.setattr(vo, "_piper_available", lambda: False)
    monkeypatch.setattr(vo.shutil, "which", lambda name: None)
    monkeypatch.setattr(vo.time, "sleep", lambda s: None)

    def boom(*args, **kwargs):
        raise RuntimeError("auth failed token supersecretvalue99")

    monkeypatch.setattr(vo, "_edge", boom)
    with caplog.at_level(logging.WARNING):
        result = vo.make_voiceover(["hello world"], str(tmp_path))
    assert result["status"] == "FAILED"
    assert "supersecretvalue99" not in caplog.text
    assert "[redacted]" in caplog.text


def test_sound_manager_failure_logs_redacted(caplog, monkeypatch):
    import scripts.sound_manager as sm

    monkeypatch.setenv("SOUNDMANAGER_TEST_SECRET", "supersecretvalue77")

    def boom(*args, **kwargs):
        raise RuntimeError("ffmpeg exploded supersecretvalue77")

    monkeypatch.setattr(sm.subprocess, "run", boom)
    out = sm._generate_synthetic_track("rain", "volume=0.5", duration=5)
    assert out is None
    assert "supersecretvalue77" not in caplog.text
    assert "[redacted]" in caplog.text
