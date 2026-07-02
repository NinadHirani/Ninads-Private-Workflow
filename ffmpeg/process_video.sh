#!/usr/bin/env bash
# FFmpeg Video Processing Script - AI Shorts Factory
# Converts raw video into 1080x1920 vertical format for YouTube Shorts.

set -e

INPUT_FILE="$1"
OUTPUT_FILE="$2"
DURATION="${3:-30}"

if [ -z "$INPUT_FILE" ] || [ -z "$OUTPUT_FILE" ]; then
    echo "Usage: ./process_video.sh <input_file> <output_file> [duration_sec]"
    exit 1
fi

if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: Input file '$INPUT_FILE' does not exist."
    exit 1
fi

mkdir -p "$(dirname "$OUTPUT_FILE")"

echo "Processing video '$INPUT_FILE' -> '$OUTPUT_FILE' (Target duration: ${DURATION}s, Resolution: 1080x1920)..."

# Check if audio stream exists
HAS_AUDIO=$(ffprobe -i "$INPUT_FILE" -show_streams -select_streams a -loglevel error | wc -l || echo "0")

if [ "$HAS_AUDIO" -gt 0 ]; then
    AUDIO_FILTER="-af loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st=$(($DURATION - 2)):d=2"
else
    # Generate silent audio track if original video has no audio
    AUDIO_FILTER="-f lavfi -i anullsrc=channel_layout=stereo:sample_rate=44100"
fi

ffmpeg -y \
    -i "$INPUT_FILE" \
    -t "$DURATION" \
    -vf "scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1" \
    -c:v libx264 \
    -preset fast \
    -crf 22 \
    -c:a aac \
    -b:a 192k \
    -movflags +faststart \
    "$OUTPUT_FILE"

echo "FFmpeg processing complete: $OUTPUT_FILE"
