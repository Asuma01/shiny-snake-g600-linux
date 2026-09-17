#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

name=G600-Display-for-Linux-rc1-x86_64
binary=dist/G600-Display-for-Linux-ubuntu22-x86_64
ffmpeg_source=dist/ffmpeg-9.0.1.tar.xz

[[ -x "$binary" && -f "$ffmpeg_source" ]] || {
    echo "Build the executable and provide the FFmpeg source archive first." >&2
    exit 1
}
printf '%s  %s\n' \
    cf38e0e28c7e5605942c4a77755349b0145804a397af37eb1fb4c77cb237f635 \
    "$ffmpeg_source" | sha256sum -c - > /dev/null

staging=$(mktemp -d "dist/.${name}.XXXXXX")
trap 'rm -rf "$staging"' EXIT
package="$staging/$name"
mkdir "$package"

install -m 755 "$binary" "$package/G600-Display-for-Linux"
install -m 644 README.md LICENSE LICENSE_SCOPE.md THIRD_PARTY_NOTICES.md \
    70-g600-display.rules "$package/"
install -m 644 "$ffmpeg_source" "$package/"
mkdir "$package/third_party"
cp -a third_party/* "$package/third_party/"

(
    cd "$package"
    find . -type f ! -name SHA256SUMS -print0 | sort -z | xargs -0 sha256sum > SHA256SUMS
)

tar --sort=name --mtime='UTC 2026-09-17' --owner=0 --group=0 \
    --numeric-owner -C "$staging" -czf "dist/$name.tar.gz" "$name"
(cd dist && sha256sum "$name.tar.gz" > "$name.tar.gz.sha256")
echo "Created dist/$name.tar.gz"
