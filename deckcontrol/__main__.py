import sys
import threading
import webbrowser

from . import paths


def _linux_autostart(enable=None):
    """XDG autostart entry (~/.config/autostart). No arg: query; True/False: set."""
    import os
    f = os.path.join(os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")), "autostart", "deckcontrol.desktop")
    if enable is None:
        return os.path.exists(f)
    if enable:
        os.makedirs(os.path.dirname(f), exist_ok=True)
        launcher = os.environ.get("DECKCONTROL_LAUNCHER") or sys.executable
        with open(f, "w") as fh:
            fh.write("[Desktop Entry]\nType=Application\nName=DeckControl\nExec=%s --minimized\nIcon=deckcontrol\n"
                     "Terminal=false\nX-GNOME-Autostart-enabled=true\n" % launcher)
    elif os.path.exists(f):
        os.remove(f)


def _autostart(enable=None):
    """Login item: Windows HKCU Run / Linux XDG autostart. No arg: query; True/False: set."""
    if sys.platform != "win32":
        return _linux_autostart(enable)
    import winreg
    key, name = r"Software\Microsoft\Windows\CurrentVersion\Run", "DeckControl"
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key, 0, winreg.KEY_ALL_ACCESS) as k:
        if enable is None:
            try:
                winreg.QueryValueEx(k, name)
                return True
            except FileNotFoundError:
                return False
        if enable:
            winreg.SetValueEx(k, name, 0, winreg.REG_SZ, '"%s" --minimized' % sys.executable)
        else:
            try:
                winreg.DeleteValue(k, name)
            except FileNotFoundError:
                pass


def main():
    paths.ensure()
    from .engine import Engine
    from .server import make_server

    engine = Engine()
    srv, port, token, warn = make_server(engine, engine.cfg.get("port", 8765))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    url = "http://127.0.0.1:%d/?t=%s" % (port, token)
    print("DeckControl running – editor:", url, flush=True)
    if warn:
        print("WARNING:", warn, flush=True)
    if "--no-browser" not in sys.argv and "--minimized" not in sys.argv and engine.cfg.get("open_browser", True):
        webbrowser.open(url)

    try:
        import pystray
        from PIL import Image, ImageDraw

        im = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.rounded_rectangle([4, 4, 60, 60], 10, fill="#1f6feb")
        for r in range(2):
            for c in range(3):
                d.rectangle([12 + c * 14, 16 + r * 18, 22 + c * 14, 28 + r * 18], fill="white")

        def pause(icon, item):
            engine.paused = not engine.paused

        items = [
            pystray.MenuItem("Open DeckControl", lambda i, it: webbrowser.open(url), default=True),
            pystray.MenuItem("Pause actions", pause, checked=lambda it: engine.paused)]
        if sys.platform in ("win32", "linux"):
            label = "Start with Windows" if sys.platform == "win32" else "Start at login"
            items.append(pystray.MenuItem(label, lambda i, it: _autostart(not _autostart()),
                                          checked=lambda it: _autostart()))

        def toggle_browser(icon, item):
            engine.cfg["open_browser"] = not engine.cfg.get("open_browser", True)
            engine.save()

        def open_data(icon, item):
            webbrowser.open("file://" + paths.DATA)

        items += [
            pystray.MenuItem("Open editor on launch", toggle_browser,
                             checked=lambda it: engine.cfg.get("open_browser", True)),
            pystray.MenuItem("Open data folder", open_data)]
        menu = pystray.Menu(*items, pystray.MenuItem("Quit", lambda i, it: i.stop()))
        pystray.Icon("DeckControl", im, "DeckControl", menu).run()
    except Exception as e:  # headless fallback
        print("(no tray icon: %s) – press Ctrl+C to quit" % e)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
