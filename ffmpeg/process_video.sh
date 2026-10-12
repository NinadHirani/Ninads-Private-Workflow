#!/usr/bin/env bash
# FFmpeg Video Processing Script - AI Shorts Factory
# Turns a raw clip into a 1080x1920 vertical Short or Reel: centre crop, trim,
# loudness-normalised audio with a fade out (or a silent track if the source has none).
# Styles (EDIT_STYLE): cinematic (smooth, default) or brainrot (push-in zoom,
# punchier colours, deep-fried grain, big caption, snappy ending).

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

# Editing style: cinematic keeps the original smooth look; brainrot adds a slow
# push-in zoom, punchier colours, film grain, an optional big caption and a snappy 0.4s ending.
STYLE="${EDIT_STYLE:-cinematic}"
STYLE_VIDEO=""
FADE_D="2"
case "$STYLE" in
    brainrot)
        Z_EXPR="1+0.18*on/(30*${LEN})"
        STYLE_VIDEO="zoompan=z=${Z_EXPR}:x=iw/2-(iw/zoom/2):y=ih/2-(ih/zoom/2):d=1:s=1080x1920:fps=30,eq=saturation=1.45:contrast=1.25,rgbashift=rh=3:bv=-3,noise=alls=7:allf=t"
        # Big meme-style caption (CAPTION_TEXT=topic or phrase), when a font is available.
        CAPTION_TEXT="${CAPTION_TEXT:-}"
        if [ -n "$CAPTION_TEXT" ]; then
            SAFE_TEXT=$(printf '%s' "$CAPTION_TEXT" | tr '[:lower:]' '[:upper:]' | tr -cd 'A-Z0-9 !?&+.' | cut -c1-60)
            FONT_FILE=""
            [ -f /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf ] && FONT_FILE=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
            if [ -z "$FONT_FILE" ]; then
                FONT_FILE=$(fc-match -f '%{file}' 'sans:bold' 2>/dev/null || true)
            fi
            # Only burn the caption when this ffmpeg build actually has drawtext.
            if [ -n "$FONT_FILE" ] && [ -f "$FONT_FILE" ] && ffmpeg -hide_banner -filters 2>/dev/null | grep -qw drawtext; then
                STYLE_VIDEO="${STYLE_VIDEO},drawtext=fontfile=${FONT_FILE}:text='${SAFE_TEXT}':fontsize=110:fontcolor=white:borderw=8:bordercolor=black:x=(w-text_w)/2:y=h-430"
            fi
        fi
        FADE_D="0.4"
        ;;
    cinematic|*)
        ;;
esac

FADE_START=$(awk -v l="$LEN" -v d="$FADE_D" 'BEGIN { s = l - d; if (s < 0) s = 0; printf "%.2f", s }')

VIDEO_FILTER="scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30"
if [ -n "$STYLE_VIDEO" ]; then
    VIDEO_FILTER="${VIDEO_FILTER},${STYLE_VIDEO}"
fi

# Optional channel-logo watermark on every Short (LOGO_FILE=path/to/logo.png).
# Position: bottom_right (default), bottom_left, top_right, top_left. Width is a % of frame width.
LOGO_FILE="${LOGO_FILE:-}"
LOGO_POSITION="${LOGO_POSITION:-bottom_right}"
LOGO_WIDTH_PCT="${LOGO_WIDTH_PCT:-15}"
LOGO_OPACITY="${LOGO_OPACITY:-0.85}"
LOGO_ARGS=()
LOGO_FILTER_ARGS=()
if [ -n "$LOGO_FILE" ] && [ -f "$LOGO_FILE" ]; then
    LOGO_MARGIN=$(( 1080 * 5 / 100 ))
    LOGO_W=$(( 1080 * LOGO_WIDTH_PCT / 100 ))
    case "$LOGO_POSITION" in
        bottom_left)  LOGO_X="x=${LOGO_MARGIN}:y=H-h-${LOGO_MARGIN}" ;;
        top_right)    LOGO_X="x=W-w-${LOGO_MARGIN}:y=${LOGO_MARGIN}" ;;
        top_left)     LOGO_X="x=${LOGO_MARGIN}:y=${LOGO_MARGIN}" ;;
        *)            LOGO_X="x=W-w-${LOGO_MARGIN}:y=H-h-${LOGO_MARGIN}" ;;
    esac
    LOGO_ARGS=(-i "$LOGO_FILE")
    VIDEO_MAP=()
    LOGO_FILTER_ARGS=(-filter_complex "[0:v]${VIDEO_FILTER}[base];[1:v]scale=${LOGO_W}:-1,format=rgba,colorchannelmixer=aa=${LOGO_OPACITY}[wm];[base][wm]overlay=${LOGO_X}[vout]" -map "[vout]")
else
    VIDEO_MAP=(-map 0:v:0)
    LOGO_FILTER_ARGS=(-vf "$VIDEO_FILTER")
fi
HAS_AUDIO=$(ffprobe -v error -select_streams a -show_entries stream=index -of csv=p=0 "$INPUT_FILE" 2>/dev/null | head -n 1 || true)

echo "Processing video '$INPUT_FILE' -> '$OUTPUT_FILE' (${LEN}s, 1080x1920, style: ${STYLE})..."

if [ -n "$HAS_AUDIO" ]; then
    ffmpeg -hide_banner -loglevel error -y \
        -i "$INPUT_FILE" ${LOGO_ARGS[@]+"${LOGO_ARGS[@]}"} \
        -t "$LEN" \
        "${VIDEO_MAP[@]}" -map 0:a:0 \
        "${LOGO_FILTER_ARGS[@]}" \
        -af "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st=${FADE_START}:d=${FADE_D}" \
        -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
        -c:a aac -b:a 192k -ar 44100 \
        -movflags +faststart \
        "$OUTPUT_FILE"
else
    # No audio in the source: add a silent stereo track so every Short has one.
    ffmpeg -hide_banner -loglevel error -y \
        -i "$INPUT_FILE" ${LOGO_ARGS[@]+"${LOGO_ARGS[@]}"} \
        -f lavfi -i "anullsrc=channel_layout=stereo:sample_rate=44100" \
        -t "$LEN" \
        "${VIDEO_MAP[@]}" -map 1:a:0 \
        "${LOGO_FILTER_ARGS[@]}" \
        -c:v libx264 -preset fast -crf 22 -pix_fmt yuv420p \
        -c:a aac -b:a 128k \
        -shortest \
        -movflags +faststart \
        "$OUTPUT_FILE"
fi

echo "FFmpeg processing complete: $OUTPUT_FILE"
