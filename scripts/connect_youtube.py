#!/usr/bin/env python3
"""
Connect YouTube - AI Shorts Factory
Connects your YouTube channel once with Google's own sign-in page and saves the
resulting refresh token into .env, so uploads work from then on with no login.

Before running: put your free API project's client id and secret in .env as
YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET
(https://console.cloud.google.com -> APIs & Services -> Credentials -> OAuth client,
type Desktop app; enable the YouTube Data API v3; add http://localhost:PORT as a
redirect URI when Google asks). Then:

    python scripts/connect_youtube.py
"""

import os
import sys
import json
import logging

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger("connect_youtube")
SCOPE = "https://www.googleapis.com/auth/youtube.upload"


def real_value(name: str):
    value = (os.getenv(name) or "").strip()
    if not value or value.startswith(("your_", "mock_")):
        return None
    return value


def _save_env(key: str, value: str) -> str:
    env_path = os.path.join(ROOT, ".env")
    lines = []
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            lines = [l.rstrip("\n") for l in f if not l.strip().startswith(f"{key}=")]
    lines.append(f"{key}={value}")
    with open(env_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    return env_path


def connect() -> dict:
    client_id = real_value("YOUTUBE_CLIENT_ID")
    client_secret = real_value("YOUTUBE_CLIENT_SECRET")
    if not (client_id and client_secret):
        return {
            "status": "FAILED",
            "error": ("Put your free API project's YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET in .env first. "
                      "Google Cloud Console -> APIs & Services -> Credentials -> create an OAuth client (Desktop app), "
                      "enable YouTube Data API v3. That part is a one-time setup on Google's site."),
        }

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        return {"status": "FAILED",
                "error": "google-auth-oauthlib is not installed. Run: pip install google-auth-oauthlib"}

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    }
    flow = InstalledAppFlow.from_client_config(client_config, scopes=[SCOPE])
    creds = flow.run_local_server(port=0, prompt="consent",
                                  access_type="offline",
                                  authorization_prompt_message="Signing in to connect your YouTube channel...")

    if not creds.refresh_token:
        return {"status": "FAILED",
                "error": ("Google did not return a refresh token. Revoke this app's access at "
                          "myaccount.google.com/permissions and run connect again.")}

    env_path = _save_env("YOUTUBE_REFRESH_TOKEN", creds.refresh_token)
    return {
        "status": "SUCCESS",
        "message": f"Channel connected. Refresh token saved to {env_path}. Uploads will now work with no further sign-in.",
    }


def main():
    result = connect()
    print(json.dumps(result, indent=2))
    sys.exit(0 if result["status"] == "SUCCESS" else 1)


if __name__ == "__main__":
    main()
