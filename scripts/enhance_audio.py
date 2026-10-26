#!/usr/bin/env python3
"""
Enhance audio quality of Sinhala voice recordings using ffmpeg.

Applies three filters in sequence:
  1. highpass=f=80       — cut sub-80 Hz rumble/handling noise
  2. afftdn=nr=20:nf=-40 — FFT-based noise reduction (nr=20 chosen by listening test)
  3. loudnorm            — EBU R128 loudness normalisation to -16 LUFS

Note: silenceremove is not applied — the recordings are so quiet (~-44 dB mean)
that any reasonable threshold also strips the speech itself.

Originals are never modified. Output goes to a separate directory.
Already-processed files are skipped (idempotent).

Usage:
    python scripts/enhance_audio.py
    python scripts/enhance_audio.py --src A_raw/ankiweb-vocab/audio \
                                     --dst data/audio_enhanced
    python scripts/enhance_audio.py --force   # reprocess everything
"""

import argparse
import subprocess
import sys
from pathlib import Path


FILTERS = ",".join([
    "highpass=f=80",
    "afftdn=nr=20:nf=-40",
    "loudnorm=I=-16:TP=-1.5:LRA=11",
    # silenceremove is intentionally omitted: these recordings are so quiet that
    # the filter treats speech as silence and strips the whole clip.
])


def enhance(src: Path, dst: Path) -> bool:
    """Run ffmpeg on src → dst. Returns True on success."""
    result = subprocess.run(
        [
            "ffmpeg", "-y",
            "-i", str(src),
            "-af", FILTERS,
            "-codec:a", "libmp3lame",
            "-q:a", "2",          # VBR ~190 kbps — better than original 64 kbps CBR
            str(dst),
        ],
        capture_output=True,
    )
    if result.returncode != 0:
        print(f"    ERROR: {result.stderr.decode().splitlines()[-1]}")
        return False
    return dst.exists()


def main():
    parser = argparse.ArgumentParser(description="Enhance Sinhala voice recordings")
    parser.add_argument("--src",   default="A_raw/ankiweb-vocab/audio",
                        help="Source directory (default: A_raw/ankiweb-vocab/audio)")
    parser.add_argument("--dst",   default="B_parsed/ankiweb-vocab/audio_enhanced",
                        help="Output directory (default: B_parsed/ankiweb-vocab/audio_enhanced)")
    parser.add_argument("--force", action="store_true",
                        help="Reprocess files that already exist in output")
    args = parser.parse_args()

    src_dir = Path(args.src)
    dst_dir = Path(args.dst)

    if not src_dir.is_dir():
        print(f"ERROR: source directory not found: {src_dir}")
        sys.exit(1)

    dst_dir.mkdir(parents=True, exist_ok=True)

    files = sorted(src_dir.glob("*.mp3"))
    if not files:
        print(f"No .mp3 files found in {src_dir}")
        sys.exit(0)

    ok = skipped = failed = 0
    for src in files:
        dst = dst_dir / src.name
        if dst.exists() and not args.force:
            skipped += 1
            continue
        print(f"  {src.name}", end=" → ", flush=True)
        if enhance(src, dst):
            print("ok")
            ok += 1
        else:
            failed += 1

    print(f"\nDone: {ok} enhanced, {skipped} already done, {failed} failed.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
