"""Built-in action library."""
import json
import os
import subprocess
import sys
import time
import urllib.request
import webbrowser

from .api import action, Param

WIN = sys.platform == "win32"
MAC = sys.platform == "darwin"

_kb = None


def kb():
    global _kb
    if _kb is None:
        from pynput.keyboard import Controller
        _kb = Controller()
    return _kb


def _key(name):
    from pynput.keyboard import Key
    n = name.strip().lower()
    alias = {"ctrl": "ctrl", "control": "ctrl", "alt": "alt", "option": "alt", "opt": "alt",
             "shift": "shift", "cmd": "cmd", "win": "cmd", "meta": "cmd", "super": "cmd",
             "esc": "esc", "escape": "esc", "return": "enter", "del": "delete", "pgup": "page_up",
             "pgdn": "page_down", "plus": "+"}
    n = alias.get(n, n)
    if len(n) == 1:
        return n
    if n == "+":
        return "+"
    return getattr(Key, n)


def press_combo(combo):
    parts = [p for p in combo.replace(" ", "").split("+") if p] if combo.strip() != "+" else ["+"]
    if combo.endswith("++"):
        parts = [p for p in combo[:-2].split("+") if p] + ["+"]
    keys = [_key(p) for p in parts]
    c = kb()
    for k in keys:
        c.press(k)
    time.sleep(0.02)
    for k in reversed(keys):
        c.release(k)


MAC_MEDIA = {"media_play_pause": 16, "media_next": 17, "media_previous": 18,
             "media_volume_up": 0, "media_volume_down": 1, "media_volume_mute": 7}


def mac_trusted(prompt=False):
    """Is this app allowed to send synthetic key events (Accessibility permission)?"""
    if not MAC:
        return True
    try:
        from ApplicationServices import AXIsProcessTrustedWithOptions, kAXTrustedCheckOptionPrompt
        return bool(AXIsProcessTrustedWithOptions({kAXTrustedCheckOptionPrompt: bool(prompt)}))
    except Exception:
        return True


def mac_media(code):
    """Real hardware-style media key (play/next/volume...) via a system-defined event."""
    from AppKit import NSEvent, NSSystemDefined
    from Quartz import CGEventPost, kCGHIDEventTap
    for down in (True, False):
        flags = 0xA00 if down else 0xB00
        ev = NSEvent.otherEventWithType_location_modifierFlags_timestamp_windowNumber_context_subtype_data1_data2_(
            NSSystemDefined, (0, 0), flags, 0, 0, None, 8, (code << 16) | flags, -1)
        CGEventPost(kCGHIDEventTap, ev.CGEvent())


def tap_media(name):
    if MAC:
        mac_media(MAC_MEDIA[name])
        return
    from pynput.keyboard import Key
    k = getattr(Key, name)
    c = kb()
    c.press(k)
    c.release(k)


def run_shell(cmd):
    if WIN:
        subprocess.Popen(cmd, shell=True, creationflags=0x08000000)
    else:
        subprocess.Popen(cmd, shell=True)


def open_path(p):
    if WIN:
        os.startfile(p)  # noqa
    elif MAC:
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


# ---------------------------------------------------------------- keyboard
@action("hotkey", "Keyboard shortcut", "Keyboard", icon="⌨",
        params=[Param("keys", "Keys", "keys", "ctrl+shift+m", help="e.g. ctrl+c, cmd+shift+4, f13, alt+tab")],
        desc="Press a key combination.")
def a_hotkey(ctx, p):
    press_combo(p["keys"])


@action("type_text", "Type text", "Keyboard", icon="🔤",
        params=[Param("text", "Text", "textarea", ""), Param("enter", "Press Enter after", "bool", False)])
def a_type(ctx, p):
    kb().type(p["text"])
    if p.get("enter"):
        press_combo("enter")


@action("scroll", "Mouse scroll", "Keyboard", icon="🖱",
        params=[Param("amount", "Lines (negative = down)", "number", 3),
                Param("horizontal", "Horizontal", "bool", False)],
        desc="Great on a knob: use a negative number on the counter-clockwise turn.")
def a_scroll(ctx, p):
    from pynput.mouse import Controller
    m = Controller()
    n = int(float(p["amount"]))
    m.scroll(n if p.get("horizontal") else 0, 0 if p.get("horizontal") else n)


# ---------------------------------------------------------------- media
def _media(name):
    def f(ctx, p):
        tap_media(name)
    return f


for _id, _lbl, _k, _ic in [
        ("media_play_pause", "Play / Pause", "media_play_pause", "⏯"),
        ("media_next", "Next track", "media_next", "⏭"),
        ("media_prev", "Previous track", "media_previous", "⏮"),
        ("vol_up", "Volume up", "media_volume_up", "🔊"),
        ("vol_down", "Volume down", "media_volume_down", "🔉"),
        ("vol_mute", "Mute", "media_volume_mute", "🔇")]:
    action(_id, _lbl, "Media", icon=_ic)(_media(_k))


def _mac_volume(delta):
    out = subprocess.run(["osascript", "-e", "output volume of (get volume settings)"],
                         capture_output=True, text=True).stdout.strip()
    if out.isdigit():
        subprocess.run(["osascript", "-e", "set volume output volume %d" % max(0, min(100, int(out) + delta))])
    else:  # output device has no software volume (HDMI / some DACs): use the media keys
        mac_media(MAC_MEDIA["media_volume_up" if delta > 0 else "media_volume_down"])


if MAC:
    action("vol_up", "Volume up", "Media", icon="🔊")(lambda ctx, p: _mac_volume(5))
    action("vol_down", "Volume down", "Media", icon="🔉")(lambda ctx, p: _mac_volume(-5))


# ---------------------------------------------------------------- system
@action("launch", "Launch app / open file", "System", icon="🚀",
        params=[Param("path", "Path or app", "path", ""), Param("args", "Arguments", "text", "")],
        desc="Start a program, or open any file/folder with its default app.")
def a_launch(ctx, p):
    path, args = p["path"], p.get("args", "")
    if args:
        if MAC and path.endswith(".app"):
            subprocess.Popen(["open", "-a", path, "--args"] + args.split())
        else:
            run_shell(f'"{path}" {args}')
    else:
        open_path(path)


@action("url", "Open website", "System", icon="🌐", params=[Param("url", "URL", "text", "https://")])
def a_url(ctx, p):
    webbrowser.open(p["url"])


@action("command", "Run shell command", "System", icon="💻",
        params=[Param("cmd", "Command", "textarea", "")],
        desc="Runs in the background through your shell.")
def a_cmd(ctx, p):
    run_shell(p["cmd"])


@action("lock", "Lock computer", "System", icon="🔒")
def a_lock(ctx, p):
    if WIN:
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"])
    elif MAC:
        subprocess.Popen(["pmset", "displaysleepnow"])
    else:
        run_shell("loginctl lock-session")


@action("delay", "Wait", "Flow", icon="⏱", params=[Param("ms", "Milliseconds", "number", 500)])
def a_delay(ctx, p):
    time.sleep(float(p["ms"]) / 1000)


@action("http", "HTTP request", "Network", icon="📡",
        params=[Param("method", "Method", "select", "GET", ["GET", "POST", "PUT", "DELETE"]),
                Param("url", "URL", "text", "http://"),
                Param("headers", "Headers (JSON)", "textarea", ""),
                Param("body", "Body", "textarea", "")],
        desc="Call webhooks / REST APIs.")
def a_http(ctx, p):
    hdr = json.loads(p["headers"]) if p.get("headers", "").strip() else {}
    body = p.get("body", "").encode() if p.get("body") else None
    req = urllib.request.Request(p["url"], data=body, method=p["method"], headers=hdr)
    urllib.request.urlopen(req, timeout=10).read()


@action("homeassistant", "Home Assistant service", "Network", icon="🏠",
        params=[Param("base", "HA URL", "text", "http://homeassistant.local:8123"),
                Param("token", "Long-lived token", "text", ""),
                Param("service", "Service (domain.service)", "text", "light.toggle"),
                Param("data", "Service data (JSON)", "textarea", '{"entity_id": "light.desk"}')])
def a_ha(ctx, p):
    dom, svc = p["service"].split(".", 1)
    req = urllib.request.Request(
        f'{p["base"].rstrip("/")}/api/services/{dom}/{svc}', data=(p["data"] or "{}").encode(), method="POST",
        headers={"Authorization": "Bearer " + p["token"], "Content-Type": "application/json"})
    urllib.request.urlopen(req, timeout=10).read()


# ---------------------------------------------------------------- deck itself
@action("goto_page", "Go to page", "Deck", icon="📄", params=[Param("page", "Page name", "text", "main")])
def a_goto(ctx, p):
    ctx.goto_page(p["page"])


@action("page_next", "Next page", "Deck", icon="➡")
def a_pn(ctx, p):
    ctx.engine.step_page(1)


@action("page_prev", "Previous page", "Deck", icon="⬅")
def a_pp(ctx, p):
    ctx.engine.step_page(-1)


@action("home_page", "Back to first page", "Deck", icon="🏠")
def a_home(ctx, p):
    ctx.engine.goto_page(None)


@action("profile", "Switch profile", "Deck", icon="🗂", params=[Param("name", "Profile name", "text", "Default")])
def a_prof(ctx, p):
    ctx.engine.set_profile(p["name"])


@action("brightness", "Deck brightness", "Deck", icon="💡",
        params=[Param("mode", "Mode", "select", "step", ["step", "set"]),
                Param("value", "Amount (step may be negative)", "number", 10)],
        desc="Use +10 / -10 'step' on a knob to dim and brighten the screens.")
def a_bright(ctx, p):
    ctx.deck_brightness(p["value"], relative=p["mode"] == "step")
