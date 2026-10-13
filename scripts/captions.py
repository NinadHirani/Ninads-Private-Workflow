#!/usr/bin/env python3
"""
Caption Builder - AI Shorts Factory
Word timings -> ASS caption file: big bold white text, thick black outline,
grouped a few words at a time, burned near the lower third. attentioncompound style.
"""
import os
import logging

logger = logging.getLogger("captions")

FONTSIZE = int(os.getenv("CAPTION_FONTSIZE", "84"))
MARGIN_V = int(os.getenv("CAPTION_MARGIN_V", "480"))
MAX_WORDS = int(os.getenv("CAPTION_MAX_WORDS", "4"))
MAX_SEC = float(os.getenv("CAPTION_MAX_SEC", "2.2"))

HEADER = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,DejaVu Sans,{fontsize},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,-1,0,0,0,100,100,0,0,1,7,0,2,60,60,{marginv},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def _ts(sec: float) -> str:
    sec = max(0.0, sec)
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    cs = int(round((sec - int(sec)) * 100))
    if cs == 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _group(words: list) -> list:
    cues = []
    cur = []
    for item in words:
        if isinstance(item, dict):
            w, s, e = item.get("word", ""), item.get("start", 0), item.get("end", 0)
        elif isinstance(item, (list, tuple)) and len(item) >= 3:
            w, s, e = item[0], item[1], item[2]
        else:
            continue
        if cur and (len(cur) >= MAX_WORDS or (s - cur[-1][2]) > 0.35 or (s - cur[0][1]) > MAX_SEC):
            cues.append((" ".join(x[0] for x in cur), cur[0][1], cur[-1][2]))
            cur = []
        cur.append((w, s, e))
    if cur:
        cues.append((" ".join(x[0] for x in cur), cur[0][1], cur[-1][2]))
    return [c for c in cues if c[0].strip()]


def build_ass(words, out_path: str) -> bool:
    """True when a word-timed ASS file was written; False when words are missing."""
    if not words:
        return False
    cues = _group(words)
    if not cues:
        return False
    lines = [HEADER.format(fontsize=FONTSIZE, marginv=MARGIN_V)]
    for text, start, end in cues:
        end = max(end, start + 0.3)
        safe = text.replace("{", "(").replace("}", ")")
        lines.append(f"Dialogue: 0,{_ts(start)},{_ts(end)},Cap,,0,0,0,,{safe}")
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    logger.info("Caption file written: %s (%d cues)", out_path, len(cues))
    return True


def fallback_ass(text_lines: list, total_len: float, out_path: str) -> bool:
    """No word timings: spread the words evenly across the voiceover length."""
    words = []
    per = []
    for line in text_lines:
        ws = str(line).split()
        for w in ws:
            per.append(max(0.16, 0.32 + 0.03 * len(w)))
    total_weight = sum(per)
    if not per or total_len <= 0:
        return False
    t = 0.0
    for w, d in zip([w for line in text_lines for w in str(line).split()], per):
        words.append((w, t, t + d))
        t += d
    scale = (total_len - 0.2) / t if t > 0 else 1.0
    words = [(w, round(s * scale, 2), round(e * scale, 2)) for w, s, e in words]
    return build_ass(words, out_path)


def main():
    import argparse
    import json
    parser = argparse.ArgumentParser(description="Build an ASS caption file from word timings")
    parser.add_argument("--words", type=str, required=True, help="JSON list of [word, start, end]")
    parser.add_argument("--out", type=str, required=True)
    parser.add_argument("--total-len", type=float, default=0)
    parser.add_argument("--fallback-text", type=str, default="", help="JSON list of lines, used when words are empty")
    args = parser.parse_args()
    words = json.loads(args.words)
    ok = build_ass(words, args.out)
    if not ok and args.fallback_text:
        ok = fallback_ass(json.loads(args.fallback_text), args.total_len, args.out)
    print(json.dumps({"status": "SUCCESS" if ok else "EMPTY", "file": args.out if ok else ""}))


if __name__ == "__main__":
    main()
