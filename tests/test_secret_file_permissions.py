"""Secret files must be readable by the owner only.

.env holds real secrets (YOUTUBE_CLIENT_SECRET, YOUTUBE_REFRESH_TOKEN,
IG_PASSWORD) and logs/instagram_session.json holds Instagram login cookies.
Both were written with the process umask, which typically leaves them
group/world readable (0644). These tests pin the hardening: writes end at
0600 whatever the umask is.
"""
import os
import stat

import pytest

import scripts.connect_youtube as cy
import scripts.instagram_uploader as ig


def test_save_env_restricts_permissions_and_preserves_lines(monkeypatch, tmp_path):
    monkeypatch.setattr(cy, "ROOT", str(tmp_path))
    env_path = tmp_path / ".env"
    env_path.write_text(
        "OTHER_SETTING=1\n# a comment stays\nYOUTUBE_REFRESH_TOKEN=old-token\nLAST=2\n",
        encoding="utf-8",
    )
    os.chmod(env_path, 0o666)  # simulate the loose pre-existing state

    saved = cy._save_env("YOUTUBE_REFRESH_TOKEN", "new-token-value")

    assert saved == str(env_path)
    assert stat.S_IMODE(os.stat(saved).st_mode) == 0o600
    text = env_path.read_text(encoding="utf-8")
    assert "OTHER_SETTING=1" in text
    assert "# a comment stays" in text
    assert "LAST=2" in text
    assert "new-token-value" in text
    assert "old-token" not in text


def test_save_env_creates_new_file_at_0600(monkeypatch, tmp_path):
    monkeypatch.setattr(cy, "ROOT", str(tmp_path))
    saved = cy._save_env("YOUTUBE_REFRESH_TOKEN", "fresh-token")
    assert os.path.exists(saved)
    assert stat.S_IMODE(os.stat(saved).st_mode) == 0o600
    assert "YOUTUBE_REFRESH_TOKEN=fresh-token" in open(saved, encoding="utf-8").read()


def test_harden_session_file(monkeypatch, tmp_path):
    path = tmp_path / "instagram_session.json"
    path.write_text("{}", encoding="utf-8")
    os.chmod(path, 0o644)
    ig._harden(str(path))
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600


def test_backup_session_is_hardened(monkeypatch, tmp_path):
    session = tmp_path / "instagram_session.json"
    session.write_text("{}", encoding="utf-8")
    os.chmod(session, 0o644)
    monkeypatch.setattr(ig, "SESSION_FILE", str(session))

    ig._backup_session_file("test")

    assert not session.exists()
    backups = list(tmp_path.glob("instagram_session.json.bak-test-*"))
    assert len(backups) == 1
    assert stat.S_IMODE(os.stat(backups[0]).st_mode) == 0o600


def test_harden_survives_unsupported_chmod(monkeypatch, tmp_path, caplog):
    path = tmp_path / "x.json"
    path.write_text("{}", encoding="utf-8")

    def boom(p, mode):
        raise OSError("chmod not supported here")

    monkeypatch.setattr(ig.os, "chmod", boom)
    ig._harden(str(path))  # must not raise; warns instead
    assert any("restrict permissions" in r.getMessage() for r in caplog.records)
