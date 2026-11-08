#!/usr/bin/env bash
# Full pipeline for one 3D explainer:  ./make_video.sh cpu [work_dir]
#   1. voiceover  (local Kokoro TTS -> voice.wav + timings.json)
#   2. 3D frames  (three.js scene in headless Chromium, synced to timings.json)
#   3. captions   (word-highlighted .ass)
#   4. final mux  (captions burned in, voice + ducked music, loudness normalised)
# Needs: ffmpeg, node + playwright, a Python venv with kokoro-onnx + soundfile, and the
# Kokoro model files (KOKORO_DIR, see README).
set -euo pipefail
PART=${1:?part name, e.g. cpu}
HERE=$(cd "$(dirname "$0")" && pwd)
WORK=${2:-$HERE/out/$PART}
KOKORO_DIR=${KOKORO_DIR:-$HERE/models}
PY=${KOKORO_PY:-python3}
JOBS=${JOBS:-3}
MUSIC=${MUSIC:-$HERE/../../../resource/songs/output000.mp3}
mkdir -p "$WORK/parts"

[ -f "$WORK/timings.json" ] || "$PY" "$HERE/tts.py" "$HERE/$PART/script.json" "$WORK" \
  --model "$KOKORO_DIR/kokoro-v1.0.onnx" --voices "$KOKORO_DIR/voices-v1.0.bin"
DUR=$(python3 -c "import json;print(json.load(open('$WORK/timings.json'))['duration'])")

# Render in JOBS parallel chunks (whole seconds so chunk frames line up).
STEP=$(python3 -c "import math;print(math.ceil($DUR/$JOBS))")
: > "$WORK/parts/list.txt"
for ((i = 0; i < JOBS; i++)); do
  S=$((i * STEP)); E=$(python3 -c "print(min($S+$STEP, $DUR))")
  [ -f "$WORK/parts/p_$S.mp4" ] || node "$HERE/render.mjs" --page "$PART/scene.html" --data "$WORK/timings.json" \
    --start "$S" --end "$E" --out "$WORK/parts/p_$S.mp4" > "$WORK/parts/log_$S.txt" 2>&1 &
  echo "file 'p_$S.mp4'" >> "$WORK/parts/list.txt"
done
wait

python3 "$HERE/captions.py" "$WORK/timings.json" "$WORK/captions.ass"
FO=$(python3 -c "print($DUR-2.5)")
ffmpeg -y -loglevel error -f concat -safe 0 -i "$WORK/parts/list.txt" -i "$WORK/voice.wav" -stream_loop -1 -i "$MUSIC" \
  -filter_complex "[0:v]ass='$WORK/captions.ass'[v];\
[2:a]atrim=0:$DUR,asetpts=N/SR/TB,volume=0.22,afade=t=in:d=1.5,afade=t=out:st=$FO:d=2.5[m];\
[1:a]aresample=48000,asplit[vo][sc];[m]aresample=48000[m48];\
[m48][sc]sidechaincompress=threshold=0.02:ratio=8:attack=15:release=450[md];\
[vo][md]amix=inputs=2:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[a]" \
  -map "[v]" -map "[a]" -t "$DUR" -c:v libx264 -preset slow -crf 18 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -movflags +faststart "$WORK/${PART}_explainer.mp4"
echo "done: $WORK/${PART}_explainer.mp4"
