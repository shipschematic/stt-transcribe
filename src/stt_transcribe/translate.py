"""Translate subtitle files with the upstream subtitle-translator CLI."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path
from typing import Sequence

REPO_URL = "https://github.com/rockbenben/subtitle-translator.git"


def default_translator_dir() -> Path:
    cache_root = Path(
        os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache"
    )
    return cache_root / "stt-transcribe" / "subtitle-translator"


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    update_default = os.environ.get(
        "SUBTITLE_TRANSLATOR_UPDATE", ""
    ).lower() in {"1", "true", "yes"}

    parser = argparse.ArgumentParser(
        description=(
            "Translate SRT files with the subtitle-translator CLI. "
            "Without paths, every .srt under --input-dir is translated."
        )
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="SRT files or directories. Defaults to --input-dir.",
    )
    parser.add_argument(
        "--input-dir",
        default="output",
        help="Directory scanned when no paths are given (default: output).",
    )
    parser.add_argument(
        "-t",
        "--target-lang",
        default="zh",
        help="Target language code (default: zh).",
    )
    parser.add_argument(
        "-f",
        "--source-lang",
        default=None,
        help="Source language code. Omit to auto-detect.",
    )
    parser.add_argument(
        "-s",
        "--settings",
        default=None,
        help="Settings JSON exported from the subtitle-translator web UI.",
    )
    parser.add_argument(
        "-m",
        "--method",
        default=None,
        help="Translation service, e.g. gtxFreeAPI, deepseek, llm.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Model name override for the chosen service.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="API key override for the chosen service.",
    )
    parser.add_argument(
        "--translator-dir",
        default=os.environ.get("SUBTITLE_TRANSLATOR_DIR"),
        help=(
            "Path to a subtitle-translator checkout. Default: "
            "${XDG_CACHE_HOME:-~/.cache}/stt-transcribe/subtitle-translator."
        ),
    )
    parser.add_argument(
        "--update-cli",
        action="store_true",
        default=update_default,
        help="Run git pull before translating.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Retranslate files whose target output already exists.",
    )
    return parser.parse_args(argv)


def collect_srt_files(
    paths: Sequence[str], default_dir: str
) -> list[Path]:
    roots = [Path(value).expanduser() for value in paths]
    if not roots:
        roots = [Path(default_dir).expanduser()]

    candidates: list[Path] = []
    for root in roots:
        if root.is_dir():
            candidates.extend(sorted(root.rglob("*.srt")))
        elif root.is_file() and root.suffix.lower() == ".srt":
            candidates.append(root)
        else:
            raise SystemExit(f"Not an SRT file or directory: {root}")

    files: list[Path] = []
    seen: set[Path] = set()
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            files.append(resolved)
    return files


def prepare_cli(translator_dir: Path, update: bool) -> None:
    """Clone the translator repo and install dependencies on first use."""
    missing = [
        tool for tool in ("git", "node", "yarn") if shutil.which(tool) is None
    ]
    if missing:
        raise SystemExit(
            "Missing required tools: "
            + ", ".join(missing)
            + ". Install git, Node.js >= 24, and Yarn 1.x."
        )

    cli_file = translator_dir / "scripts" / "cli.ts"
    if not cli_file.is_file():
        print(f"Installing subtitle-translator CLI -> {translator_dir}")
        translator_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["git", "clone", "--depth", "1", REPO_URL, str(translator_dir)],
            check=True,
        )
    elif update:
        print(f"Updating subtitle-translator CLI -> {translator_dir}")
        subprocess.run(
            ["git", "-C", str(translator_dir), "pull", "--ff-only"],
            check=True,
        )

    tsx_dir = translator_dir / "node_modules" / "tsx"
    if not tsx_dir.is_dir():
        print("Installing CLI dependencies (yarn)...")
        subprocess.run(
            ["yarn", "install", "--frozen-lockfile"],
            cwd=str(translator_dir),
            check=True,
        )


def target_path(source: Path, target_lang: str) -> Path:
    return source.with_name(f"{source.stem}.{target_lang}{source.suffix}")


def translate_file(
    source: Path,
    target: Path,
    args: argparse.Namespace,
    translator_dir: Path,
) -> tuple[str, str]:
    """Run the upstream CLI for one file. Returns (status, detail)."""
    command = [
        "yarn",
        "cli",
        "-i",
        str(source),
        "-t",
        args.target_lang,
    ]
    if args.source_lang:
        command.extend(["-f", args.source_lang])
    if args.settings:
        command.extend(["-s", str(Path(args.settings).expanduser())])
    if args.method:
        command.extend(["-m", args.method])
    if args.model:
        command.extend(["--model", args.model])
    if args.api_key:
        command.extend(["--api-key", args.api_key])

    result = subprocess.run(
        command,
        cwd=str(translator_dir),
        check=False,
        capture_output=True,
        text=True,
    )
    detail = (result.stderr or result.stdout or "").strip()[-300:]

    if result.returncode == 0 and target.exists():
        return "ok", ""
    if result.returncode == 1 and target.exists():
        return "partial", detail
    if result.returncode == 0:
        return (
            "fail",
            f"CLI finished but {target.name} was not created. {detail}",
        )
    return "fail", f"exit={result.returncode} {detail}".strip()


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)

    translator_dir = Path(
        args.translator_dir or default_translator_dir()
    ).expanduser().resolve()

    srt_files = collect_srt_files(args.paths, args.input_dir)
    print(f"Found {len(srt_files)} srt files")
    print("-" * 60)

    pending: list[tuple[Path, Path]] = []
    for source in srt_files:
        if source.name.endswith(f".{args.target_lang}.srt"):
            continue
        target = target_path(source, args.target_lang)
        if target.exists() and not args.force:
            continue
        pending.append((source, target))

    if pending:
        try:
            prepare_cli(translator_dir, args.update_cli)
        except (OSError, subprocess.CalledProcessError) as exc:
            print(f"FAIL  could not prepare subtitle-translator CLI: {exc}")
            return 1

    ok = skip = partial = fail = 0
    failures: list[tuple[Path, str]] = []

    for index, source in enumerate(srt_files, 1):
        target = target_path(source, args.target_lang)
        label = source.name

        if source.name.endswith(f".{args.target_lang}.srt"):
            print(f"[{index}/{len(srt_files)}] SKIP  {label} (target file)")
            skip += 1
            continue
        if target.exists() and not args.force:
            print(f"[{index}/{len(srt_files)}] SKIP  {label}")
            skip += 1
            continue

        print(f"[{index}/{len(srt_files)}] RUN   {label}")
        status, detail = translate_file(
            source, target, args, translator_dir
        )
        if status == "ok":
            print(f"        ok    -> {target.name}")
            ok += 1
        elif status == "partial":
            print(f"        PARTIAL -> {target.name} (some lines kept source)")
            partial += 1
        else:
            print(f"        FAIL  {detail}")
            failures.append((source, detail))
            fail += 1

    print("-" * 60)
    print(
        f"DONE: {ok} ok | {partial} partial | "
        f"{skip} skipped | {fail} failed"
    )
    if failures:
        print("\nFailures:")
        for path, error in failures:
            print(f"  {path.name}")
            print(f"    {error}")

    return 1 if failures else 0
