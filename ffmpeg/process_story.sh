#!/usr/bin/env bash
# Story Reel Builder - AI Shorts Factory
# Cuts several stock clips together, adds the deep-fried brainrot look,
# burns word-timed captions, lays the AI voiceover over it, and adds the logo.
# Usage: process_story.sh <output> <duration> <voiceover> [captions.ass] <clip1> [clip2] ...

set -euo pipefail

OUT="${1:?Usage: process_story.sh <output> <duration> <voiceover> [captions.ass] <clip1> [clip2] ...}"
LEN="${2:?Missing duration}"
VO="${3:?Missing voiceover}"
shift 3
ASS=""
if [ $# -ge 1 ] && [ "${1##*.}" = "ass" ]; then
    ASS="$1"; shift
fi
if [ $# -lt 1 ]; then
    echo "Error: at least one clip is required." >&2
    exit 1
fi
for f in "$VO"; do
    [ -f "$f" ] || { echo "Error: voiceover '$f' not found." >&2; exit 1; }
done
for c in "$@"; do
    [ -f "$c" ] || { echo "Error: clip '$c' not found." >&2; exit 1; }
done
command -v ffmpeg >/dev/null 2>&1 || { echo "Error: ffmpeg not installed." >&2; exit 127; }
command -v ffprobe >/dev/null 2>&1 || { echo "Error: ffprobe not installed." >&2; exit 127; }

mkdir -p "$(dirname "$OUT")"

VODEV=$(ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 "$VO" 2>/dev/null || echo 0)
LEN=$(awk -v a="$LEN" -v b="${VODEV:-0}" 'BEGIN { if (b + 0 > 0 && b + 0 < a + 0) a = b; printf "%.2f", a }')
N=$#
CLIP_LEN=$(awk -v l="$LEN" -v n="$N" 'BEGIN { printf "%.2f", l / n }')
FADE_START=$(awk -v l="$LEN" 'BEGIN { printf "%.2f", l - 0.5 }')

LOGO_FILE="${LOGO_FILE:-}"
LOGO_OPACITY="${LOGO_OPACITY:-0.85}"
LOGO_WIDTH_PCT="${LOGO_WIDTH_PCT:-15}"
LOGO_MARGIN=$(( 1080 * 5 / 100 ))
LOGO_W=$(( 1080 * LOGO_WIDTH_PCT / 100 ))
# Square the logo into LOGO_W x LOGO_W and use numeric overlay positions:
# some FFmpeg builds reject W/H expressions in this multi-input graph.
LOGO_H=$(( 1080 * LOGO_WIDTH_PCT / 100 ))
LOGO_X="x=$(( 1080 - LOGO_W - LOGO_MARGIN )):y=$(( 1920 - LOGO_H - LOGO_MARGIN ))"

INPUTS=()
FILTER=""
i=0
for c in "$@"; do
    INPUTS+=(-i "$c")
    # Push-in zoom runs per clip (before the concat), the deep-fry look runs on the joined reel.
    FILTER+="[$i:v]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,setsar=1,fps=30,trim=duration=${CLIP_LEN},setpts=PTS-STARTPTS,zoompan=z='1+0.15*on/(30*${LEN})':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s=1080x1920:fps=30[v$i];"
    i=$((i + 1))
done
CONCAT_IN=""
for k in $(seq 0 $((N - 1))); do CONCAT_IN+="[v$k]"; done
FILTER+="${CONCAT_IN}concat=n=${N}:v=1:a=0[cat];"
FILTER+="[cat]eq=saturation=1.3:contrast=1.15,rgbashift=rh=2:bv=-2[fx];"
LAST="[fx]"
if [ -n "$ASS" ] && [ -f "$ASS" ] && ffmpeg -hide_banner -filters 2>/dev/null | grep -qw subtitles; then
    ASS_ESC=$(printf '%s' "$ASS" | sed "s/:/\\\\:/g")
    FILTER+="[fx]subtitles=filename='${ASS_ESC}'[sub];"
    LAST="[sub]"
fi

VO_IDX=$N
LOGO_ARGS=()
if [ -n "$LOGO_FILE" ] && [ -f "$LOGO_FILE" ]; then
    LOGO_ARGS=(-i "$LOGO_FILE")
    LOGO_IDX=$N
    VO_IDX=$((N + 1))
    FILTER+="[${LOGO_IDX}:v]scale=${LOGO_W}:${LOGO_H},format=rgba,colorchannelmixer=aa=${LOGO_OPACITY}[wm];"
    FILTER+="${LAST}[wm]overlay=${LOGO_X}[vout]"
else
    FILTER+="${LAST}null[vout]"
fi

echo "Building story reel -> '$OUT' (${LEN}s, ${N} clips, captions: ${ASS:-none}, logo: ${LOGO_FILE:+yes})..."

ffmpeg -hide_banner -loglevel error -y \
    ${INPUTS[@]+"${INPUTS[@]}"} "${LOGO_ARGS[@]+"${LOGO_ARGS[@]}"}" -i "$VO" \
    -filter_complex "$FILTER" \
    -map "[vout]" -map "${VO_IDX}:a" \
    -t "$LEN" \
    -af "loudnorm=I=-16:TP=-1.5:LRA=11,afade=t=out:st=${FADE_START}:d=0.5" \
    -c:v libx264 -preset fast -crf 22 -maxrate 6M -bufsize 12M -pix_fmt yuv420p \
    -c:a aac -b:a 192k -ar 44100 \
    -movflags +faststart \
    "$OUT"

echo "Story reel complete: $OUT"
