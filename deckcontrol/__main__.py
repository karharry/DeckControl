import sys
import threading
import webbrowser

from . import paths


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

        menu = pystray.Menu(
            pystray.MenuItem("Open DeckControl", lambda i, it: webbrowser.open(url), default=True),
            pystray.MenuItem("Pause actions", pause, checked=lambda it: engine.paused),
            pystray.MenuItem("Quit", lambda i, it: i.stop()))
        pystray.Icon("DeckControl", im, "DeckControl", menu).run()
    except Exception as e:  # headless fallback
        print("(no tray icon: %s) – press Ctrl+C to quit" % e)
        try:
            threading.Event().wait()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
