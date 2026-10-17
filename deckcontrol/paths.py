"""Portable locations: everything lives beside the executable (or the source tree)."""
import os
import sys


def app_dir():
    if getattr(sys, "frozen", False):
        d = os.path.dirname(os.path.abspath(sys.executable))
        # macOS .app bundle: keep data next to the .app, not inside it
        if sys.platform == "darwin" and ".app/Contents/MacOS" in d:
            d = os.path.dirname(os.path.dirname(os.path.dirname(d)))
        return d
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def resource_dir():
    """Read-only bundled resources (web UI)."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", app_dir())
    return os.path.dirname(os.path.abspath(__file__))


DATA = os.path.join(app_dir(), "DeckControl-data")
CONFIG = os.path.join(DATA, "config.json")
PLUGINS = os.path.join(DATA, "plugins")
TEMPLATES = os.path.join(DATA, "templates")
IMAGES = os.path.join(DATA, "images")
TOKEN = os.path.join(DATA, ".token")
AUTH = os.path.join(DATA, "auth.json")
LOG = os.path.join(DATA, "deckcontrol.log")


def ensure():
    import shutil
    for d in (DATA, PLUGINS, TEMPLATES, IMAGES):
        os.makedirs(d, exist_ok=True)
    seed = os.path.join(resource_dir(), "seed")
    for sub, dst in (("plugins", PLUGINS), ("templates", TEMPLATES)):
        src = os.path.join(seed, sub)
        if os.path.isdir(src):
            for f in os.listdir(src):
                if not os.path.exists(os.path.join(dst, f)):
                    shutil.copy(os.path.join(src, f), os.path.join(dst, f))
