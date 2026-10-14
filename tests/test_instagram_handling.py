"""Instagram uploader: safe failure handling and stale-session recovery (no live calls)."""
import os
import sys
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from scripts import instagram_uploader as ig  # noqa: E402


class FakeError(Exception):
    pass


def test_missing_credentials_fails_cleanly(monkeypatch):
    monkeypatch.delenv("IG_USERNAME", raising=False)
    monkeypatch.delenv("IG_PASSWORD", raising=False)
    monkeypatch.setenv("SHORTS_MOCK", "0")
    result = ig.connect_instagram()
    assert result["status"] == "FAILED"
    assert "IG_USERNAME" in result["error"]


def test_mock_upload_never_touches_client(monkeypatch):
    monkeypatch.setenv("SHORTS_MOCK", "1")

    def boom():
        raise AssertionError("mock mode must not create a real client")

    monkeypatch.setattr(ig, "_new_client", boom)
    real_file = os.path.join("/tmp", "ig_mock_upload_input.mp4")
    with open(real_file, "wb") as f:
        f.write(b"0")
    result = ig.upload_to_instagram(real_file, caption="c")
    assert result["status"] == "SUCCESS"
    assert result["mode"] == "MOCK"
    assert result["instagram_url"].startswith("https://instagram.com/reel/mock_")


def test_upload_missing_file_fails_cleanly(monkeypatch):
    monkeypatch.setenv("SHORTS_MOCK", "0")
    result = ig.upload_to_instagram("/nonexistent/video.mp4")
    assert result["status"] == "FAILED"
    assert "not found" in result["error"]


def test_two_factor_reported_with_guidance(monkeypatch):
    """A 2FA error surfaces as FAILED with next steps, not a raw stack string."""
    monkeypatch.setenv("SHORTS_MOCK", "0")
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "pass")
    monkeypatch.setattr(ig, "SESSION_FILE", os.path.join("/tmp", "ig_tests_none.json"))

    class TwoFactorRequired(FakeError):
        pass

    def failing_client():
        cl = type("C", (), {})()
        cl.login = lambda u, p: (_ for _ in ()).throw(TwoFactorRequired("two_factor required"))
        return cl

    monkeypatch.setattr(ig, "_new_client", failing_client)
    result = ig.connect_instagram()
    assert result["status"] == "FAILED"
    assert result["error_kind"] == "two_factor"
    assert "two-factor" in result["error"].lower()
    assert "Detail:" in result["error"]


def test_challenge_reported_with_guidance(monkeypatch):
    monkeypatch.setenv("SHORTS_MOCK", "0")
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "pass")
    monkeypatch.setattr(ig, "SESSION_FILE", os.path.join("/tmp", "ig_tests_none.json"))

    class ChallengeRequired(FakeError):
        pass

    def failing_client():
        cl = type("C", (), {})()
        cl.login = lambda u, p: (_ for _ in ()).throw(ChallengeRequired("checkpoint challenge required"))
        return cl

    monkeypatch.setattr(ig, "_new_client", failing_client)
    result = ig.connect_instagram()
    assert result["status"] == "FAILED"
    assert result["error_kind"] == "challenge"
    assert "verify" in result["error"].lower()


def test_stale_session_recovered(monkeypatch, tmp_path):
    """A cached session that fails login is backed up (never deleted) and a fresh login succeeds."""
    session = tmp_path / "instagram_session.json"
    session.write_text('{"stale": true}')
    monkeypatch.setenv("SHORTS_MOCK", "0")
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "pass")
    monkeypatch.setattr(ig, "SESSION_FILE", str(session))
    monkeypatch.setattr(ig, "_backup_session_file", ig._backup_session_file)

    clients = []

    def make_client(username, broken):
        class Client:
            def __init__(self):
                self.username = username

            def load_settings(self, path):
                assert path == str(session)

            def login(self, u, p):
                if broken and os.path.exists(str(session)):
                    raise FakeError("connection reset on cached session")

            def dump_settings(self, path):
                with open(path, "w") as f:
                    f.write('{"fresh": true}')

        c = Client()
        clients.append(c)
        return c

    def fake_client():
        if len(clients) == 0:
            return make_client("stale_user", broken=True)
        return make_client("fresh_user", broken=False)

    monkeypatch.setattr(ig, "_new_client", fake_client)
    result = ig.connect_instagram()
    assert result["status"] == "SUCCESS"
    assert result["login"] == "fresh"
    assert len(clients) == 2, "a second, fresh login should have been attempted"
    # the recovered client, not the stale one, must be the active one afterwards
    assert result["username"] == "fresh_user"
    backups = [f for f in os.listdir(tmp_path) if f.startswith("instagram_session.json.bak-")]
    assert backups, "the stale session should be backed up, not silently deleted"


def test_recovered_client_used_for_upload(monkeypatch, tmp_path):
    """After session recovery, the upload runs on the fresh client, never the stale one."""
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"0")
    session = tmp_path / "instagram_session.json"
    session.write_text('{"stale": true}')
    monkeypatch.setenv("SHORTS_MOCK", "0")
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "pass")
    monkeypatch.setattr(ig, "SESSION_FILE", str(session))

    uploads = []

    class Media:
        code = "abc123"
        pk = 42

    def make_client(number):
        class Client:
            def __init__(self):
                self.username = "user"

            def load_settings(self, path):
                pass

            def login(self, u, p):
                if number == 1:
                    raise FakeError("connection reset on cached session")

            def dump_settings(self, path):
                pass

            def clip_upload(self, path, **kwargs):
                if number == 1:
                    raise AssertionError("the stale client must never upload")
                uploads.append(number)
                return Media()

        return Client()

    # first call -> client 1 (fails login), second call inside recovery -> client 2
    counter = {"n": 0}

    def fake_client2():
        counter["n"] += 1
        return make_client(counter["n"])

    monkeypatch.setattr(ig, "_new_client", fake_client2)
    result = ig.upload_to_instagram(str(video), caption="c")
    assert result["status"] == "SUCCESS"
    assert uploads == [2], "the upload must land on the recovered fresh client"
    assert result["instagram_url"].endswith("/reel/abc123/")


def test_friendly_error_redacts_password(monkeypatch):
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "supersecretpw")
    out = ig._friendly_error(Exception("login failed: password supersecretpw rejected"))
    assert "supersecretpw" not in out
    assert "[redacted]" in out
    assert "Exception" in out, "the exception class name stays for diagnosis"


def test_friendly_error_redacts_long_tokens(monkeypatch):
    token = "A" * 60
    out = ig._friendly_error(Exception(f"session cookie {token} expired"))
    assert token not in out
    assert "[redacted-token]" in out


def test_connect_error_never_echoes_password(monkeypatch):
    monkeypatch.setenv("SHORTS_MOCK", "0")
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "supersecretpw")
    monkeypatch.setattr(ig, "SESSION_FILE", os.path.join("/tmp", "ig_tests_none.json"))

    def failing_client():
        cl = type("C", (), {})()
        cl.login = lambda u, p: (_ for _ in ()).throw(Exception("bad login: password supersecretpw"))
        return cl

    monkeypatch.setattr(ig, "_new_client", failing_client)
    result = ig.connect_instagram()
    assert result["status"] == "FAILED"
    assert "supersecretpw" not in result["error"]


def test_unreadable_session_backed_up(monkeypatch, tmp_path):
    session = tmp_path / "instagram_session.json"
    session.write_text("not-json-garbage")
    monkeypatch.setenv("SHORTS_MOCK", "0")
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "pass")
    monkeypatch.setattr(ig, "SESSION_FILE", str(session))

    class Client:
        username = "user"

        def load_settings(self, path):
            raise ValueError("bad session file")

        def login(self, u, p):
            return True

        def dump_settings(self, path):
            with open(path, "w") as f:
                f.write('{"fresh": true}')

    monkeypatch.setattr(ig, "_new_client", lambda: Client())
    result = ig.connect_instagram()
    assert result["status"] == "SUCCESS"
    assert session.read_text() == '{"fresh": true}'


def test_connect_failure_never_logs_password(monkeypatch, caplog):
    """Raw exception text must not reach the log; only redacted detail may."""
    import logging
    monkeypatch.setenv("SHORTS_MOCK", "0")
    monkeypatch.setenv("IG_USERNAME", "user")
    monkeypatch.setenv("IG_PASSWORD", "supersecretpw")
    monkeypatch.setattr(ig, "SESSION_FILE", os.path.join("/tmp", "ig_tests_none.json"))

    def failing_client():
        cl = type("C", (), {})()
        cl.login = lambda u, p: (_ for _ in ()).throw(Exception("bad login: password supersecretpw"))
        return cl

    monkeypatch.setattr(ig, "_new_client", failing_client)
    with caplog.at_level(logging.ERROR, logger="instagram_uploader"):
        ig.connect_instagram()
    assert "supersecretpw" not in caplog.text
