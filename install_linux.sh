#!/bin/bash
# Installs DeckControl for the current user: ~/.local/opt/DeckControl + application menu entry.
set -e
cd "$(dirname "$0")"
D="${DECKCONTROL_DIR:-$HOME/.local/opt/DeckControl}"
mkdir -p "$D" ~/.local/share/applications ~/.local/share/icons/hicolor/64x64/apps ~/.local/share/fonts
rm -rf "$D/deckcontrol"
cp -r deckcontrol run.py requirements.txt "$D/"
find "$D" -name __pycache__ -prune -exec rm -rf {} +
# system site packages: the tray needs PyGObject (gi) from the distro
[ -d "$D/venv" ] || python3 -m venv --system-site-packages "$D/venv"
"$D/venv/bin/pip" install -q hidapi pillow pystray python-xlib six
"$D/venv/bin/pip" install -q --no-deps pynput   # its evdev dependency needs compiling and isn't used here
# colour emoji font for key images (needs a bitmap font; Fedora's COLRv1 build renders blank)
if [ ! -e ~/.local/share/fonts/NotoColorEmoji.ttf ]; then
  f=$(ls /usr/share/fonts/*/NotoColorEmoji.ttf /var/lib/flatpak/runtime/org.freedesktop.Platform/*/*/active/files/share/fonts/noto-emoji/NotoColorEmoji.ttf 2>/dev/null | head -1)
  [ -n "$f" ] && cp "$f" ~/.local/share/fonts/ && fc-cache -f ~/.local/share/fonts || echo "note: no NotoColorEmoji.ttf found; install a colour emoji font"
fi
"$D/venv/bin/python" - <<'PY'
from PIL import Image, ImageDraw
import os
im = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rounded_rectangle([4, 4, 60, 60], 10, fill="#1f6feb")
for r in range(2):
    for c in range(3):
        d.rectangle([12 + c * 14, 16 + r * 18, 22 + c * 14, 28 + r * 18], fill="white")
im.save(os.path.expanduser("~/.local/share/icons/hicolor/64x64/apps/deckcontrol.png"))
PY
cat > "$D/DeckControl" <<L
#!/bin/sh
cd "$D"
export DECKCONTROL_LAUNCHER="$D/DeckControl"
exec "$D/venv/bin/python" run.py "\$@"
L
chmod +x "$D/DeckControl"
cat > ~/.local/share/applications/deckcontrol.desktop <<L
[Desktop Entry]
Type=Application
Name=DeckControl
Comment=Controller software for the Ajazz AKP03E
Exec=$D/DeckControl
Path=$D
Icon=deckcontrol
Terminal=false
Categories=Utility;
L
update-desktop-database ~/.local/share/applications 2>/dev/null || true
echo "Installed. Start DeckControl from the application menu."
