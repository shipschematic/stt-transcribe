"""Transcribe media files into SRT and plain-text transcripts."""

from __future__ import annotations

import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Sequence

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".webm", ".m4v"}
AUDIO_EXTS = {".wav", ".mp3", ".flac", ".ogg", ".m4a", ".aac", ".wma"}
MEDIA_EXTS = VIDEO_EXTS | AUDIO_EXTS


def srt_time(seconds: float) -> str:
    """Format seconds as an SRT timestamp."""
    total_ms = int(seconds * 1000)
    hours, remainder = divmod(total_ms, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, millis = divmod(remainder, 1_000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def find_media(input_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in input_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in MEDIA_EXTS
    )


def output_paths(
    media_path: Path, input_dir: Path, output_dir: Path
) -> tuple[Path, Path]:
    """Return the .txt and .srt paths for a media file, preserving subfolders."""
    relative = media_path.relative_to(input_dir).with_suffix("")
    base = output_dir / relative
    return base.with_suffix(".txt"), base.with_suffix(".srt")


def write_transcript(txt_path: Path, srt_path: Path, segments: list) -> None:
    txt_path.parent.mkdir(parents=True, exist_ok=True)

    with txt_path.open("w", encoding="utf-8") as handle:
        for segment in segments:
            handle.write(segment.text.strip() + "\n")

    with srt_path.open("w", encoding="utf-8") as handle:
        for index, segment in enumerate(segments, 1):
            handle.write(f"{index}\n")
            handle.write(
                f"{srt_time(segment.start)} --> {srt_time(segment.end)}\n"
            )
            handle.write(f"{segment.text.strip()}\n\n")


def transcribe_audio(model, audio_path: Path, language: str | None):
    segments, info = model.transcribe(str(audio_path), language=language)
    return list(segments), info


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe media files into SRT and plain-text transcripts."
    )
    parser.add_argument(
        "--input-dir",
        default="input",
        help="Directory containing media files (default: input).",
    )
    parser.add_argument(
        "--output-dir",
        default="output",
        help="Directory for .txt and .srt output (default: output).",
    )
    parser.add_argument(
        "--model",
        default="base",
        help="faster-whisper model name or path (default: base).",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Source language code. Omit to auto-detect.",
    )
    parser.add_argument(
        "--device",
        default="auto",
        help="Inference device: auto, cpu, or cuda (default: auto).",
    )
    parser.add_argument(
        "--compute-type",
        default="default",
        help="faster-whisper compute type (default: default).",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing transcripts instead of skipping them.",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    input_dir = Path(args.input_dir).expanduser()
    output_dir = Path(args.output_dir).expanduser()
    input_dir.mkdir(parents=True, exist_ok=True)
    output_dir.mkdir(parents=True, exist_ok=True)

    media_files = find_media(input_dir)
    print(f"Found {len(media_files)} media files")
    print("-" * 60)

    if not media_files:
        return 0

    from faster_whisper import WhisperModel

    model = WhisperModel(
        args.model,
        device=args.device,
        compute_type=args.compute_type,
    )

    ok = skip = fail = 0
    failures: list[tuple[Path, str]] = []

    for index, media_path in enumerate(media_files, 1):
        relative = media_path.relative_to(input_dir)
        txt_path, srt_path = output_paths(media_path, input_dir, output_dir)

        if txt_path.exists() and srt_path.exists() and not args.force:
            print(f"[{index}/{len(media_files)}] SKIP  {relative}")
            skip += 1
            continue

        print(f"[{index}/{len(media_files)}] RUN   {relative}")
        try:
            if media_path.suffix.lower() in AUDIO_EXTS:
                segments, info = transcribe_audio(
                    model, media_path, args.language
                )
            else:
                with tempfile.TemporaryDirectory(
                    prefix="stt-transcribe-"
                ) as temp_dir:
                    wav_path = Path(temp_dir) / "audio.wav"
                    subprocess.run(
                        [
                            "ffmpeg",
                            "-y",
                            "-i",
                            str(media_path),
                            "-vn",
                            "-ac",
                            "1",
                            "-ar",
                            "16000",
                            str(wav_path),
                        ],
                        check=True,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                    segments, info = transcribe_audio(
                        model, wav_path, args.language
                    )

            write_transcript(txt_path, srt_path, segments)
            print(
                f"        ok    lang={info.language}  segs={len(segments)}"
            )
            ok += 1

        except Exception as exc:
            print(f"        FAIL  {exc}")
            failures.append((relative, repr(exc)))
            fail += 1

    print("-" * 60)
    print(f"DONE: {ok} ok | {skip} skipped | {fail} failed")
    if failures:
        print("\nFailures:")
        for path, error in failures:
            print(f"  {path}")
            print(f"    {error}")

    return 1 if failures else 0
