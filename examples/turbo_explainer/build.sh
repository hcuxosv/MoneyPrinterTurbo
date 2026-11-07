#!/usr/bin/env bash
# Build a 3D turbo short: voice-over -> 3D render -> mp4.
#   ./build.sh          "How a Turbo Works"
#   ./build.sh lag      "Turbo lag, twin-scroll and anti-lag"
#   ./build.sh sc       "Supercharger vs turbo"
#   ./build.sh rotary   "Rotary (Wankel) engine"
set -euo pipefail
cd "$(dirname "$0")"
STORY=${1:-turbo}
case "$STORY" in
  turbo) NAME=how_a_turbo_works ;;
  lag)   NAME=turbo_lag_twin_scroll_anti_lag ;;
  sc)    NAME=supercharger_vs_turbo ;;
  rotary) NAME=rotary_engine ;;
  *) echo "unknown story: $STORY (turbo|lag|sc|rotary)"; exit 1 ;;
esac
ROOT=${BUILD:-build}
BUILD=$ROOT/$STORY
MODELS=${MODELS:-$ROOT/models}
mkdir -p "$BUILD" "$MODELS"

for f in kokoro-v1.0.onnx voices-v1.0.bin; do
  [ -f "$MODELS/$f" ] || curl -fL -o "$MODELS/$f" \
    "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/$f"
done
[ -d "$ROOT/node_modules/three" ] || (cd "$ROOT" && npm init -y >/dev/null && npm i three@0.170.0)
ln -sfn ../node_modules "$BUILD/node_modules"

python3 voiceover.py --story "$STORY" --models "$MODELS" --out "$BUILD"
node render.mjs --build "$BUILD" --out "$ROOT/$NAME.mp4"
echo "Done: $ROOT/$NAME.mp4"
