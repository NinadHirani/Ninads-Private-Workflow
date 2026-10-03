#!/usr/bin/env bash
# FFmpeg Video Processing Script - AI Shorts Factory
# Turns a raw clip into a 1080x1920 vertical YouTube Short: centre crop, trim,
# loudness-normalised audio with a 2s fade out (or a silent track if the source has none).

set -euo pipefail

INPUT_FILE="${1:-}"
OUTPUT_FILE="${2:-}"
DURATION="${3:-30}"

if [ -z "$INPUT_FILE" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Usage: ./process_video.sh <input_file> <output_file> [duration_sec]" >&2
    exit 1
fi
if ! command -v ffmpeg >/dev/null 2>&1 || ! command -v ffprobe >/dev/null 2>&1; then
    echo "Error: ffmpeg and ffprobe must be installed." >&2
    exit 127
fi
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file '$INPUT_FILE' does not exist." >&2
    exit 1
fi
if ! [[ "$DURATION" =~ ^[0-9]+([.][0-9]+)?$ ]]; then
    echo "Error: duration must be a number of seconds." >&2
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

# Use the shorter of the requested length and the clip itself, so the fade lands at the real end.
SOURCE_LEN=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$INPUT_FILE" 2>/dev/null || true)
LEN=$(awk -v a="$DURATION" -v b="${SOURCE_LEN:-0}" 'BEGIN { if (b + 0 > 0 && b + 0 < a + 0) a = b; printf "%.2f", a }')
FADE_START=$(awk -v l="$LEN" 'BEGIN { s = l - 2; if (s < 0) s = 0; printf "%.2f", s }')

VIDEO_FILTER="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
HAS_AUDIO=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$INPUT_FILE" 2>/dev/null | head -n 1 || true)

echo "Processing video '$INPUT_FILE' -> '$OUTPUT_FILE' (${LEN}s, 1080x1920)..."

if [ -n "$HAS_AUDIO" ]; then
    ffmpeg -hide_banner -loglevel error -y \
        -i "$INPUT_FILE" \
        -t "$LEN" \
        -map 0:v:0 -map 0:a:0 \
        -vf "$VIDEO_FILTER" \
        -af "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st=${FADE_START}:d=2" \
        -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
        -c:a aac -b:a 192k -ar 44100 \
        -movflags +faststart \
        "$OUTPUT_FILE"
else
    # No audio in the source: add a silent stereo track so every Short has one.
    ffmpeg -hide_banner -loglevel error -y \
        -i "$INPUT_FILE" \
        -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100" \
        -t "$LEN" \
        -map 0:v:0 -map 1:a:0 \
        -vf "$VIDEO_FILTER" \
        -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
        -c:a aac -b:a 128k \
        -shortest \
        -movflags +faststart \
        "$OUTPUT_FILE"
fi

echo "FFmpeg processing complete: $OUTPUT_FILE"
