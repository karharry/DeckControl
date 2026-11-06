#!/bin/bash
# Installs DeckControl for the current user: ~/.local/opt/DeckControl + application menu entry,
# plus a udev rule (needs sudo) so your user may open the controller and send key presses.
#   ./install_linux.sh               install / update (re-run after your distro upgrades Python)
#   ./install_linux.sh --no-udev     skip the sudo step
#   ./install_linux.sh --uninstall   remove the program, menu entry, autostart and udev rule
#                                    (your settings in DeckControl-data are kept unless --purge is added)
set -e
cd "$(dirname "$0")"
D="${DECKCONTROL_DIR:-$HOME/.local/opt/DeckControl}"
APPS="${XDG_DATA_HOME:-$HOME/.local/share}/applications"
ICONS="${XDG_DATA_HOME:-$HOME/.local/share}/icons/hicolor/64x64/apps"
FONTS="${XDG_DATA_HOME:-$HOME/.local/share}/fonts"
AUTOSTART="${XDG_CONFIG_HOME:-$HOME/.config}/autostart/deckcontrol.desktop"
RULE=/etc/udev/rules.d/70-deckcontrol.rules
UDEV=1; UNINSTALL=0; PURGE=0
for a in "$@"; do
  case "$a" in
    --no-udev) UDEV=0 ;;
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    *) echo "unknown option: $a"; exit 2 ;;
  esac
done

if [ $UNINSTALL = 1 ]; then
  pkill -f "$D/venv/bin/python run.py" 2>/dev/null || true
  rm -f "$APPS/deckcontrol.desktop" "$ICONS/deckcontrol.png" "$AUTOSTART"
  if [ $PURGE = 1 ]; then rm -rf "$D"; else rm -rf "$D/deckcontrol" "$D/venv" "$D/run.py" "$D/requirements.txt" "$D/DeckControl"; fi
  if [ -e "$RULE" ]; then
    echo "Removing $RULE (sudo)"
    sudo rm -f "$RULE" && sudo udevadm control --reload
  fi
  echo "Uninstalled.$([ $PURGE = 1 ] || echo " Settings kept in $D/DeckControl-data (use --purge to delete them).")"
  exit 0
fi

# --- prerequisites -------------------------------------------------------------
missing=""
command -v python3 >/dev/null || missing="$missing python3"
python3 -c "import venv, ensurepip" 2>/dev/null || missing="$missing python3-venv(ensurepip)"
python3 -c "import gi" 2>/dev/null || missing="$missing PyGObject(python3-gobject)"
ldconfig -p 2>/dev/null | grep -q "libhidapi-hidraw" || missing="$missing libhidapi-hidraw(hidapi)"
if [ -n "$missing" ]; then
  echo "Missing:$missing"
  echo "Install them with your package manager (Fedora: dnf/rpm-ostree install python3-gobject hidapi; Debian/Ubuntu: apt install python3-venv python3-gi libhidapi-hidraw0), then re-run."
  exit 1
fi

mkdir -p "$D" "$APPS" "$ICONS" "$FONTS"
rm -rf "$D/deckcontrol"
cp -r deckcontrol run.py requirements.txt "$D/"
find "$D" -name __pycache__ -prune -exec rm -rf {} +

# The environment uses the distro's site-packages (for gi), so it must be rebuilt when system Python changes.
want=$(python3 -c 'import sys;print("%d.%d"%sys.version_info[:2])')
have=$(sed -n 's/^version = \([0-9]*\.[0-9]*\).*/\1/p' "$D/venv/pyvenv.cfg" 2>/dev/null || true)
if [ "$have" != "$want" ]; then rm -rf "$D/venv"; fi
[ -d "$D/venv" ] || python3 -m venv --system-site-packages "$D/venv"
"$D/venv/bin/pip" install -q hidapi pillow pystray python-xlib six
"$D/venv/bin/pip" install -q --no-deps pynput   # its evdev dependency needs compiling and isn't used here
"$D/venv/bin/python" -c "import PIL, pystray, pynput, gi" || { echo "Python environment is broken"; exit 1; }

# colour emoji font for key images (needs a bitmap font; COLRv1 builds render blank)
if [ ! -e "$FONTS/NotoColorEmoji.ttf" ]; then
  f=$(ls /usr/share/fonts/*/NotoColorEmoji.ttf /var/lib/flatpak/runtime/org.freedesktop.Platform/*/*/active/files/share/fonts/noto-emoji/NotoColorEmoji.ttf 2>/dev/null | head -1)
  if [ -n "$f" ]; then cp "$f" "$FONTS/" && fc-cache -f "$FONTS"; else echo "note: no NotoColorEmoji.ttf found; install a colour emoji font for emoji on the keys"; fi
fi

"$D/venv/bin/python" - "$ICONS/deckcontrol.png" <<'PY'
import sys
from PIL import Image, ImageDraw
im = Image.new("RGBA", (64, 64), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
d.rounded_rectangle([4, 4, 60, 60], 10, fill="#1f6feb")
for r in range(2):
    for c in range(3):
        d.rectangle([12 + c * 14, 16 + r * 18, 22 + c * 14, 28 + r * 18], fill="white")
im.save(sys.argv[1])
PY
cat > "$D/DeckControl" <<L
#!/bin/sh
cd "$D"
export DECKCONTROL_LAUNCHER="$D/DeckControl"
exec "$D/venv/bin/python" run.py "\$@"
L
chmod +x "$D/DeckControl"
cat > "$APPS/deckcontrol.desktop" <<L
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
update-desktop-database "$APPS" 2>/dev/null || true

# --- device permissions (udev) -------------------------------------------------
if [ $UDEV = 1 ]; then
  if cmp -s linux/70-deckcontrol.rules "$RULE" 2>/dev/null; then
    echo "udev rule already installed."
  else
    echo "Installing udev rule $RULE (needs sudo) so your user can open the controller and send key presses."
    sudo install -m 644 linux/70-deckcontrol.rules "$RULE"
    sudo rm -f /etc/udev/rules.d/70-ajazz-deckcontrol.rules   # older hand-made name
    sudo udevadm control --reload
    sudo udevadm trigger --subsystem-match=hidraw --action=change
    sudo udevadm trigger --subsystem-match=misc --action=change
  fi
else
  echo "Skipped udev rule. If DeckControl stays on \"Waiting for device\", run: sudo install -m 644 linux/70-deckcontrol.rules $RULE && sudo udevadm control --reload && sudo udevadm trigger"
fi
echo "Installed. Start DeckControl from the application menu."
