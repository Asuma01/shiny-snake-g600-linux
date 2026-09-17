#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if [[ -z "${FFMPEG_BIN:-}" || ! -x "${FFMPEG_BIN}" ]]; then
    echo "Set FFMPEG_BIN to an executable, statically linked FFmpeg build." >&2
    exit 1
fi
if [[ "$(basename "${FFMPEG_BIN}")" != "ffmpeg" ]]; then
    echo "The static FFmpeg executable must be named ffmpeg." >&2
    exit 1
fi
if readelf -l "${FFMPEG_BIN}" | grep -q INTERP; then
    echo "FFMPEG_BIN is dynamically linked; use a static build for a standalone release." >&2
    exit 1
fi

python3 -m PyInstaller --noconfirm --clean --onefile --windowed \
    --name G600-Display-for-Linux \
    --add-data "$(pwd)/assets:assets" \
    --add-data "$(pwd)/THIRD_PARTY_NOTICES.md:." \
    --add-data "$(pwd)/LICENSE:." \
    --add-data "$(pwd)/third_party:third_party" \
    --add-binary "${FFMPEG_BIN}:." \
    --distpath dist --workpath build --specpath build \
    entrypoint.py

echo "Built dist/G600-Display-for-Linux"
