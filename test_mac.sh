#!/bin/bash
# Self-test for DeckControl on macOS: installs deps in a venv, runs from source, builds the portable binary, runs it.
set -u
cd "$(dirname "$0")"
echo "== system: $(sw_vers -productVersion) $(uname -m)  python: $(python3 --version 2>&1)"
command -v python3 >/dev/null || { echo "FAIL: python3 missing (install Xcode CLT: xcode-select --install)"; exit 1; }
python3 -m venv .venv && . .venv/bin/activate || { echo "FAIL venv"; exit 1; }
pip install -q -U pip setuptools wheel 2>&1 | tail -1
pip install -q -r requirements.txt 2>&1 | tail -3
echo "== imports"
python - <<'PY'
import hid, PIL, pystray, pynput
print("hid ok, pillow", PIL.__version__)
from deckcontrol import render, device
im = render.render_key({"label":"Mute","icon":"\U0001F507","bg":"#b62324"}); print("render ok", im.size)
im.save("/tmp/dc_key.png")
print("devices found:", [(hex(d['vendor_id']),hex(d['product_id'])) for d in device.find_devices()])
PY
test_api() {  # $1 = label ; uses port 8765
  sleep 6
  echo "-- $1: /api/auth:"; curl -s localhost:8765/api/auth; echo
  T=$(cat DeckControl-data/.token 2>/dev/null || cat dist/DeckControl-data/.token)
  curl -s -c /tmp/dcjar -o /dev/null "localhost:8765/?t=$T"
  echo "-- $1: /api/state:"; curl -s -b /tmp/dcjar localhost:8765/api/state; echo
  echo "-- $1: actions:"; curl -s -b /tmp/dcjar localhost:8765/api/actions | python3 -c "import sys,json;a=json.load(sys.stdin);print(len(a),'actions;', 'vol_up' in [x['id'] for x in a])"
  echo "-- $1: preview png bytes:"; curl -s -b /tmp/dcjar -d '{"label":"Hi","icon":"X"}' localhost:8765/api/preview | wc -c
  echo "-- $1: unauth blocked:"; curl -s localhost:8765/api/state; echo
}
echo "== run from source"
python -m deckcontrol --no-browser > /tmp/dc_src.log 2>&1 &
P=$!; test_api source; kill $P 2>/dev/null; wait $P 2>/dev/null; echo "-- log:"; tail -5 /tmp/dc_src.log
echo "== build portable binary"
pip install -q pyinstaller 2>&1 | tail -1
./build_mac.sh > /tmp/dc_build.log 2>&1; tail -3 /tmp/dc_build.log
ls -la dist/ 2>/dev/null
if [ -x dist/DeckControl ]; then
  echo "== run binary"
  (cd dist && ./DeckControl --no-browser > /tmp/dc_bin.log 2>&1 &) ; test_api binary
  pkill -f "dist/DeckControl" ; pkill -x DeckControl; sleep 1; echo "-- log:"; tail -5 /tmp/dc_bin.log
  ls dist/DeckControl-data
fi
echo "== DONE"
