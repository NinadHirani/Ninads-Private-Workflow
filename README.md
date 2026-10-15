# AI Shorts Factory 🎬⚡

[![Live Web App](https://img.shields.io/badge/Live%20Mobile%20App-Install-blueviolet?logo=pwa)](https://shorts-factory-olive.vercel.app)
[![Tests](https://img.shields.io/badge/tests-164%20passing-brightgreen)]()

One command in, finished vertical shorts out: script, visuals, voiceover, edit, watermark, upload to YouTube and Instagram.

Free forever by design: Pexels/Pixabay keys, FFmpeg local, YouTube Data API free quota, Edge TTS/Piper voice, your own machine.

## Quick start

```bash
git clone https://github.com/NinadHirani/Ninads-Private-Workflow.git
cd Ninads-Private-Workflow
pip install -r requirements.txt
brew install ffmpeg          # macOS; Linux: sudo apt install ffmpeg

cp .env.example .env         # add your free keys:
#   PIXABAY_API_KEY=...      (or PEXELS_API_KEY)
#   YOUTUBE_CLIENT_ID / YOUTUBE_CLIENT_SECRET / YOUTUBE_REFRESH_TOKEN
#   IG_USERNAME / IG_PASSWORD
#   LOGO_FILE=assets/channel_logo.png
#   EDIT_STYLE=cinematic|brainrot
#   SHORTS_UI_TOKEN=choose-a-long-random-string

# One-time: connect the YouTube channel (OAuth) and/or Instagram login
python3 scripts/shortsctl.py connect --platform both

# Make one short now
python3 scripts/run_pipeline.py --topic "one-punch man anime"

# Continuous maker: start / stop / status
python3 scripts/shortsctl.py start
python3 scripts/shortsctl.py stop
python3 scripts/shortsctl.py status
```

## Web dashboard

`python3 scripts/web_ui.py` serves the dashboard on `0.0.0.0:8088` and a public install app lives at https://shorts-factory-olive.vercel.app (PWA, installable from the browser menu).

## Web UI security

The dashboard controls a real machine, so access is proof-based: a request counts as local only when BOTH the connecting socket and the Host header are loopback; every other caller must authenticate.

- Local no-token flow: on the machine itself, the dashboard works without any token, as before.
- Dashboard login (the normal path): open the dashboard and enter the token from `SHORTS_UI_TOKEN` (.env) once in the connect banner (the browser does not store it). The server checks it and returns an HttpOnly session cookie; later calls use the cookie automatically.
- The token is sent ONLY as a request header (`X-Shorts-Token:` or `Authorization: Bearer`) or in the one-time login body; it is never embedded in pages, links, responses, or logs.
- The Vercel app is a different origin, so cookies do not apply: the token you enter in the connect banner stays in the page's memory for that visit (never written to browser storage) and is sent as the `X-Shorts-Token` header on every call, and it plays media by fetching it with the token and playing the blob, since a plain `<video>` tag cannot send headers. Same-origin pages (localhost or the tunnel URL) stream media directly.
- Origin and Sec-Fetch-Site headers are never accepted as authorization (they are spoofable); the tests pin this: forged matching Origin or Sec-Fetch-Site from off-machine gets 401 on reads and POSTs.
- Static assets (the dashboard page itself) are public; every API endpoint and every media file requires a credential.
- `POST /api/session` exchanges the token for the cookie once; `DELETE /api/session` revokes it. Preflight (`OPTIONS`) answers openly but grants nothing.

### Known limitation: the dual-upload queue has no automatic drain

When a run finishes locally but the YouTube daily quota is exhausted, the video is recorded in `logs/dual_queue.json` and stays there. Nothing uploads automatically from the queue, and no automatic retry exists, by design: the entries remain pending until you handle them manually from the machine (e.g. rerun `scripts/uploader.py` or the pipeline when quota resets). The dashboard's queue view is read-only and authenticated.

## Editing styles

- `cinematic` (default): smooth 2s cross-fades, clean color.
- `brainrot`: zoom push-in, punchier saturation (1.35) and contrast (1.12), snappy 0.4s ending.

Set via `EDIT_STYLE` in .env, `editing_style` in context.json, or `--style` per run.

## Story/commentary engine

`scripts/story_pipeline.py` makes AI-scripted story/commentary reels: genre-template script, Edge TTS (Piper fallback) voiceover, word-timed burned captions, per-scene visuals with the logo watermark, then uploads to both platforms. 60s cap via `MAX_DURATION_SECONDS`.

## Tests

```bash
python3 -m pytest tests/ -q
```

164 tests cover the pipeline, uploads, auth (forged headers rejected, session lifecycle, Range streaming), and the frontend contract (no token in storage or page).
