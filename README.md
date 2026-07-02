# AI Shorts Factory 🎬⚡

Production-ready YouTube Shorts automation platform built with Docker, n8n, Python, FFmpeg, and YouTube Data API v3.

## Overview

AI Shorts Factory automatically:
- Discovers free licensed short-form videos (Pexels / Pixabay)
- Downloads raw video clips with multi-attempt exponential retry logic
- Validates resolution, aspect ratio, audio stream, and playable format
- Edits videos into 9:16 portrait format (1080x1920) with FFmpeg audio normalization
- Generates SEO-optimized titles, descriptions, and hashtags
- Uploads vertical Shorts directly to YouTube
- Logs execution status to SQLite (`logs/history.db`) & CSV (`logs/execution.csv`)
- Archives processed media safely without overwriting

---

## Project Structure

```
n8n youtube/
├── docker-compose.yml
├── .env.example
├── .env
├── .gitignore
├── README.md
├── docker/
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
│   └── archive.py
├── ffmpeg/
│   └── process_video.sh
├── prompts/
│   └── metadata_prompt.txt
├── music/
├── captions/
├── thumbnails/
└── tests/
    ├── test_content_finder.py
    ├── test_downloader.py
    ├── test_validator.py
    ├── test_editor.py
    ├── test_metadata.py
    ├── test_uploader.py
    ├── test_logger.py
    └── test_pipeline_integration.py
```

---

## Quick Start

### 1. Configure Environment Variables
Copy `.env.example` to `.env` and fill in your API credentials:
```bash
cp .env.example .env
```

### 2. Run Local Python Tests
```bash
python3 -m pytest tests/ -v
```

### 3. Start with Docker Compose
```bash
docker-compose up -d
```
Access n8n workflow dashboard at: `http://localhost:5678`

---

## Execution Pipeline Verification

You can test any script directly via CLI:
```bash
# 1. Search Content
python3 scripts/content_finder.py --topic "nature"

# 2. Download Video
python3 scripts/downloader.py --url "https://commondatastorage.googleapis.com/gtv-videos-bucket/sample/ForBiggerBlazes.mp4"

# 3. Validate Video
python3 scripts/validator.py --file "downloads/raw_*.mp4"

# 4. Edit Video (9:16 portrait)
python3 scripts/editor.py --input "downloads/raw_*.mp4"

# 5. Generate SEO Metadata
python3 scripts/metadata_generator.py --topic "nature"

# 6. Upload Short
python3 scripts/uploader.py --file "edited/short_*.mp4"

# 7. Log Execution
python3 scripts/logger.py --topic "nature" --status "SUCCESS" --yt_id "MOCK_123"

# 8. Archive Processed Files
python3 scripts/archive.py --raw "downloads/raw_*.mp4" --edited "edited/short_*.mp4"
```
