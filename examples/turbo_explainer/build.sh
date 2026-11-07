#!/usr/bin/env bash
# Build the "How a Turbo Works" 3D short: voice-over -> 3D render -> mp4.
set -euo pipefail
cd "$(dirname "$0")"
BUILD=${BUILD:-build}
MODELS=${MODELS:-$BUILD/models}
mkdir -p "$BUILD" "$MODELS"

for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [ -f "$MODELS/$f" ] || curl -fL -o "$MODELS/$f" \
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
[ -d "$BUILD/node_modules/three" ] || (cd "$BUILD" && npm init -y >/dev/null && npm i three@0.170.0)

python3 voiceover.py --models "$MODELS" --out "$BUILD"
node render.mjs --build "$BUILD" --out "$BUILD/how_a_turbo_works.mp4"
echo "Done: $BUILD/how_a_turbo_works.mp4"
