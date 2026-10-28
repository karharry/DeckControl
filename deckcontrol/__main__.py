import sys
import threading
import webbrowser

from . import paths


def _autostart(enable=None):
    """Windows login item (HKCU Run). No arg: query; True/False: set. Only meaningful for the packaged exe."""
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
    if "--no-browser" not in sys.argv and "--minimized" not in sys.argv:
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
        if sys.platform == "win32":
            items.append(pystray.MenuItem("Start with Windows", lambda i, it: _autostart(not _autostart()),
                                          checked=lambda it: _autostart()))
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
