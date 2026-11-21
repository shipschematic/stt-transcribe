# stt-transcribe

Transcribe media with [faster-whisper](https://github.com/SYSTRAN/faster-whisper),
then translate the SRT with
[subtitle-translator](https://github.com/rockbenben/subtitle-translator).

```text
input/<name>.mp4  ->  output/<name>.srt  ->  output/<name>.zh.srt
                      output/<name>.txt
```

## Why not use Whisper's built-in translation?

Whisper has a `translate` task, but it only translates speech to **English**.
It cannot produce Chinese, Japanese, or any other target language.

This project transcribes once, then translates the SRT into any language
supported by subtitle-translator (120+). It keeps the original timecodes and
adds provider choice, glossary, settings export, and bilingual output. Use
Whisper's `translate` task directly only when English is the target.

## Project layout

```text
.
├── input/                  # media files, ignored by git
├── output/                 # generated .txt, .srt, .zh.srt files, ignored by git
├── scripts/
│   ├── transcribe.sh
│   └── translate.sh
├── src/stt_transcribe/
│   ├── transcribe.py       # faster-whisper transcription
│   └── translate.py        # subtitle-translator CLI wrapper
├── .env.example
├── pyproject.toml
└── uv.lock
```

## Requirements

- [uv](https://docs.astral.sh/uv/)
- `ffmpeg` for video-to-audio conversion
- Python 3.11 (managed by uv)
- For translation only: `git`, Node.js >= 24, and Yarn 1.x
- Optional: CUDA libraries for GPU transcription. The transcribe wrapper adds
  the virtualenv's NVIDIA libraries to `LD_LIBRARY_PATH` automatically.

## Setup

```bash
uv sync
cp .env.example .env
```

Edit `.env` only if you need to override the Hugging Face cache location or
enable offline mode.

## Usage

1. Put media files in `input/`. Subdirectories are allowed and their structure
   is preserved in `output/`.

2. Transcribe:

   ```bash
   ./scripts/transcribe.sh
   ```

   This writes `<name>.txt` and `<name>.srt` to `output/`.

3. Translate the SRT files:

   ```bash
   ./scripts/translate.sh
   ```

   This writes `<name>.zh.srt` beside each source SRT in `output/`.

Existing outputs are skipped. Pass `--force` to regenerate them.

### Transcription options

```bash
./scripts/transcribe.sh --model small --language en
./scripts/transcribe.sh --input-dir media --output-dir transcripts
./scripts/transcribe.sh --help
```

### Translation options

```bash
./scripts/translate.sh -t ja
./scripts/translate.sh output/movie.srt -t ja
./scripts/translate.sh -s ~/subtitle-settings.json -m deepseek
./scripts/translate.sh --help
```

The translation CLI uses the free GTX API by default. To use another provider,
export settings JSON from the subtitle-translator web UI and pass it with
`-s`.

## Translation CLI cache

Upstream does not publish the CLI as a standalone package: `yarn cli` must run
from a full checkout. `stt-translate` keeps that checkout outside this repo at:

```text
${XDG_CACHE_HOME:-~/.cache}/stt-transcribe/subtitle-translator
```

On first use it clones the repo and runs `yarn install`. Later runs reuse it.

If you already have a checkout, move it into the cache instead of downloading
it again:

```bash
mkdir -p "${XDG_CACHE_HOME:-$HOME/.cache}/stt-transcribe"
mv /path/to/subtitle-translator \
  "${XDG_CACHE_HOME:-$HOME/.cache}/stt-transcribe/subtitle-translator"
```

Override or update it with:

```bash
./scripts/translate.sh --translator-dir /path/to/checkout
./scripts/translate.sh --update-cli
```

## Development

```bash
uv run stt-transcribe --help
uv run stt-translate --help
python -m py_compile src/stt_transcribe/*.py
```
