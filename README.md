# AI Shorts Factory 🎬⚡

[![Live Web App](https://img.shields.io/badge/Live%20Mobile%20App-Vercel-black?style=for-the-badge&logo=vercel)](https://shorts-factory-olive.vercel.app)
[![PWA](https://img.shields.io/badge/Mobile-Installable%20PWA-blue?style=for-the-badge&logo=pwa)](https://shorts-factory-olive.vercel.app)

> 📱 **Live Mobile Control Center**: [https://shorts-factory-olive.vercel.app](https://shorts-factory-olive.vercel.app)  
> Install to your iPhone or Android home screen with 1 tap using the built-in **"Install App"** shortcut button.

Production-ready YouTube Shorts & Instagram Reels automation platform built with Remotion, Docker, n8n, Python, FFmpeg, and YouTube Data API v3.

## Overview

AI Shorts Factory automatically:
- Discovers free licensed short-form videos (Pexels / Pixabay)
- Downloads raw video clips with multi-attempt exponential retry logic
- Validates resolution, aspect ratio, audio stream, and playable format
- Edits videos into 9:16 portrait format (1080x1920) with FFmpeg audio normalization
- Burns the channel logo into every Short as a watermark (when LOGO_FILE is set)
- Generates SEO-optimized titles, descriptions, and hashtags
- Uploads vertical Shorts directly to YouTube and posts the same video to Instagram as a Reel
- Logs execution status to SQLite (`logs/history.db`) & CSV (`logs/execution.csv`)
- Archives processed media safely without overwriting

---

## Project Structure

```
ai-shorts-factory/
├── docker-compose.yml
├── .env.example
├── .gitignore
├── README.md
├── context.json
├── assets/
│   └── channel_logo.png        # your channel logo, burned in as a watermark
├── docker/
│   ├── n8n/
│   │   └── Dockerfile
│   └── python/
│       ├── Dockerfile
│       └── requirements.txt
├── n8n/
│   ├── workflows/
│   │   ├── 01_Content_Finder.json
│   │   ├── 02_Downloader.json
│   │   ├── 03_Validator.json
│   │   ├── 04_Editor.json
│   │   ├── 05_Metadata.json
│   │   ├── 06_Uploader.json
│   │   └── 07_Logger.json
│   └── master_workflow.json
├── downloads/
├── edited/
├── archive/
├── logs/
├── scripts/
│   ├── content_finder.py
│   ├── downloader.py
│   ├── validator.py
│   ├── editor.py
│   ├── metadata_generator.py
│   ├── uploader.py
│   ├── logger.py
│   ├── archive.py
│   ├── run_pipeline.py
│   ├── shortsctl.py
│   ├── auto_run.py
│   ├── factory_cli.py
│   └── connect_youtube.py
├── ffmpeg/
│   └── process_video.sh
├── prompts/
│   └── metadata_prompt.txt
├── music/
├── captions/
├── thumbnails/
└── tests/
    ├── conftest.py
    ├── test_content_finder.py
    ├── test_downloader.py
    ├── test_validator.py
    ├── test_editor.py
    ├── test_metadata.py
    ├── test_uploader.py
    ├── test_logger.py
    ├── test_pipeline_integration.py
    └── test_run_pipeline.py
```

---

## Quick Start

### 1. Configure environment variables
```bash
cp .env.example .env
```
Add a free Pexels or Pixabay key (Pexels is tried first, Pixabay is the fallback) and your YouTube OAuth credentials. Missing keys are reported as errors; nothing is faked. For a dry run with no keys, set `SHORTS_MOCK=1`: the finder uses `tests/sample.mp4` (or `SHORTS_SAMPLE_VIDEO`) and the uploader returns a fake video ID instead of uploading.

### 2. Make one Short with one command
```bash
python3 scripts/run_pipeline.py --topic "ocean waves"
```
This runs every step in order (find, download, validate, edit to 1080x1920, validate, metadata, upload, log, archive) and prints a JSON summary with the YouTube link. Uploads are **private** by default so you can check each Short first; add `--privacy unlisted` or `--privacy public` when you're happy. Other options: `--duration 45` (5 to 180 seconds), `--keep-files` (skip archiving).

Test run with no keys and nothing uploaded, but real FFmpeg rendering:
```bash
SHORTS_MOCK=1 python3 scripts/run_pipeline.py --topic ocean
```
Set `SHORTS_SAMPLE_VIDEO=/path/to/clip.mp4` to test with your own clip instead of `tests/sample.mp4`.

### 3. Run the tests
```bash
pip install -r requirements.txt
python3 -m pytest tests/ -v
```
FFmpeg must be installed for the video tests (they generate `tests/sample.mp4` on first run); without it those tests are skipped. In Docker: `docker compose run --rm python_worker`.

### 4. Start n8n
```bash
docker compose up -d --build
```
Open `http://localhost:5678`, import `n8n/master_workflow.json` and activate it. It runs once a day: find, download, validate, edit, write metadata, upload, log, archive. Any failed step stops the run. The topic is set in the 01_Content_Finder, 05_Metadata and 07_Logger commands (`nature` by default). The files in `n8n/workflows/` are single-step snippets for reference; the master workflow is the one to import.

The n8n image is built from `docker/n8n/Dockerfile`, which adds Python, FFmpeg and the Python packages, because n8n's Execute Command node runs inside the n8n container. Compose also sets `NODES_EXCLUDE=[]`, since n8n 2.0 and later disable that node by default.

## Start and stop (one click each)

Set up your channel once, then let it run:

```bash
python3 scripts/shortsctl.py connect   # once: links your YouTube channel and Instagram
python3 scripts/shortsctl.py start     # makes and uploads Shorts until you stop it
python3 scripts/shortsctl.py status    # is it running? how many made today
python3 scripts/shortsctl.py stop      # finishes the current Short, then stops
```

Edit `context.json` to tell it what kind of Shorts to make. One-off runs (`run_pipeline.py`) upload **private** by default. Continuous runs (`shortsctl start`) upload private and switch to **public** automatically after `schedule_public_gap_minutes` (5 minutes by default in context.json; set it to `0` to keep them private until you switch them yourself). The mobile control center's create action also publishes **public** by default unless a privacy is passed explicitly.

Every Short also goes to Instagram as a Reel: put IG_USERNAME and IG_PASSWORD in `.env` (the same video is posted to both, and the session is cached after the first login). Instagram has no "private upload" through this route, so Reels are visible per your account's privacy: on a private account only your approved followers see them. Instagram posting uses an unofficial client, so keep `max_per_day` modest in context.json.

Every Short is capped at **60 seconds** (change it with `MAX_DURATION_SECONDS` in `.env`) to keep processing and uploads quick.

### Editing styles

Two looks, switchable per run or globally:

- `cinematic` (default): smooth, calm, 2s fade out. Good for scenic and serious content.
- `brainrot`: slow push-in zoom, punchier colours, snappy 0.4s ending. Good for fast meme-style Reels.

Set it with `EDIT_STYLE` in `.env`, `"editing_style"` in `context.json` (what the maker uses), or `--style brainrot` on a single run:
```bash
python3 scripts/run_pipeline.py --topic "ocean waves" --style brainrot
```

### Channel logo watermark

Put your logo in `assets/channel_logo.png` and add this line to `.env`:

```
LOGO_FILE=assets/channel_logo.png
```

Every Short then carries your logo (bottom right by default). Tune it with `LOGO_POSITION` (bottom_right, bottom_left, top_right, top_left), `LOGO_WIDTH_PCT` (default 15), and `LOGO_OPACITY` (default 0.85). Use a transparent-background PNG.

### Good to know
- Uploads from a YouTube API project that hasn't passed Google's audit are locked to private. Request an audit if you want public Shorts.
- The editor centre-crops to 1080x1920, trims to 30 seconds (or the clip length if shorter), normalises loudness with a 2 second fade out, and adds a silent track to clips without audio.
- Pexels and Pixabay videos are free to use, and attribution isn't required.

---

## Web UI security

The dashboard serves state-changing controls (one-click create, maker start/stop, config save), and it is open on your network with an optional fixed tunnel address. Those endpoints are protected:

- Opening the dashboard itself (from localhost, or a phone on your Wi-Fi) needs no setup: same-origin calls are allowed.
- Anything calling from outside that page (another website, a script on the LAN, or through the public tunnel) must send the token from `SHORTS_UI_TOKEN` in .env as an `X-Shorts-Token` header (or `Authorization: Bearer <token>`). With no token set, outside callers are rejected.
- If your Vercel mobile app calls the API directly, set `SHORTS_UI_TOKEN` in .env once and add the same header in the app.

Read-only views (status, logs, deliverables) stay open, but cross-origin websites get no CORS header, so a browser on another site cannot read responses.

## Running steps by hand

```bash
python3 scripts/content_finder.py --topic "nature"
python3 scripts/downloader.py --url "<video_url from the finder>"
python3 scripts/validator.py --file downloads/raw_<timestamp>.mp4
python3 scripts/editor.py --input downloads/raw_<timestamp>.mp4
python3 scripts/metadata_generator.py --topic "nature" --output logs/metadata_latest.json
python3 scripts/uploader.py --file edited/short_<timestamp>.mp4 --metadata logs/metadata_latest.json
python3 scripts/logger.py --topic "nature" --status SUCCESS --yt_id <video_id>
python3 scripts/archive.py --raw downloads/raw_<timestamp>.mp4 --edited edited/short_<timestamp>.mp4
```
Each script prints JSON on stdout (logs go to stderr) and exits non-zero on failure.

---

## AgentTown Connector Interface

For programmatic integration with AgentTown (or any orchestrator), use `scripts/factory_cli.py`. It provides a JSON-in / JSON-out stream emitting step progress events and a final result event.

```bash
# Find candidate videos
python3 scripts/factory_cli.py find --json '{"topic":"ocean waves"}'

# Produce a Short (renders and validates without uploading)
python3 scripts/factory_cli.py produce --json '{"topic":"ocean waves","duration":30,"style":"cinematic","mode":"clip"}'

# Publish a produced Short
python3 scripts/factory_cli.py publish --json '{"file":"edited/short_xxx.mp4","platform":"youtube","privacy":"private","metadata":{"title":"...","description":"...","tags":["..."]}}'

# Continuous maker status & control
python3 scripts/factory_cli.py maker --json '{"action":"status"}'
python3 scripts/factory_cli.py maker --json '{"action":"start","privacy":"private"}'
python3 scripts/factory_cli.py maker --json '{"action":"stop"}'
```
