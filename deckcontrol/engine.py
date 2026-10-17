"""Profiles, pages, event dispatch, device lifecycle."""
import copy
import glob
import importlib.util
import json
import os
import sys
import threading
import time
import traceback

from . import api, paths, render
from . import device as dev

LONG_MS = 600
KEYS = ["k1", "k2", "k3", "k4", "k5", "k6"]           # buttons with displays
PLAIN = ["b7", "b8", "b9"]                            # buttons without display
KNOBS = ["e1", "e2", "e3"]


def A(t, **params):
    return {"type": t, "params": params}


def default_config():
    mod = "cmd" if sys.platform == "darwin" else "ctrl"
    main = {"controls": {
        "k1": {"label": "Play", "icon": "⏯", "bg": "#1f6feb", "events": {"press": [A("media_play_pause")]}},
        "k2": {"label": "Prev", "icon": "⏮", "bg": "#30363d", "events": {"press": [A("media_prev")]}},
        "k3": {"label": "Next", "icon": "⏭", "bg": "#30363d", "events": {"press": [A("media_next")]}},
        "k4": {"label": "Mute", "icon": "🔇", "bg": "#b62324", "events": {"press": [A("vol_mute")]}},
        "k5": {"label": "Lock", "icon": "🔒", "bg": "#6e40c9", "events": {"press": [A("lock")]}},
        "k6": {"label": "More", "icon": "➡", "bg": "#238636", "events": {"press": [A("goto_page", page="tools")]}},
        "b7": {"events": {"press": [A("hotkey", keys=mod + "+c")]}},
        "b8": {"events": {"press": [A("hotkey", keys=mod + "+v")]}},
        "b9": {"events": {"press": [A("hotkey", keys=mod + "+z")]}},
        "e1": {"events": {"cw": [A("scroll", amount=-3)], "ccw": [A("scroll", amount=3)]}},
        "e2": {"events": {"cw": [A("vol_up")], "ccw": [A("vol_down")], "press": [A("vol_mute")]}},
        "e3": {"events": {"cw": [A("brightness", mode="step", value=10)],
                          "ccw": [A("brightness", mode="step", value=-10)]}},
    }}
    tools = {"controls": {
        "k1": {"label": "Google", "icon": "🌐", "bg": "#1a73e8", "events": {"press": [A("url", url="https://google.com")]}},
        "k6": {"label": "Back", "icon": "⬅", "bg": "#238636", "events": {"press": [A("home_page")]}},
    }}
    return {"version": 1, "brightness": 60, "port": 8765, "bind": "127.0.0.1", "input_map": {},
            "active_profile": "Default",
            "profiles": {"Default": {"match": "", "page_order": ["main", "tools"],
                                     "pages": {"main": main, "tools": tools}}}}


class Ctx:
    def __init__(self, engine, control, event):
        self.engine, self.control, self.event = engine, control, event

    def goto_page(self, name):
        self.engine.goto_page(name)

    def deck_brightness(self, v, relative=False):
        self.engine.change_brightness(float(v), relative)

    def set_label(self, text):
        c = self.engine.current_page()["controls"].setdefault(self.control, {})
        c["label"] = text
        self.engine.redraw()

    def log(self, msg):
        self.engine.log("plugin", str(msg))


class Engine:
    def __init__(self):
        paths.ensure()
        self.lock = threading.RLock()
        self.cfg = self._load()
        self.profile = self.cfg["active_profile"]
        self.page = None
        self.deck = None
        self.status = "Looking for device…"
        self.events = []       # log for UI
        self.evid = 0
        self.learn = None
        self.paused = False
        self.down_at = {}
        self.timers = {}
        self.plugin_errors = []
        self.load_plugins()
        from . import actions
        actions.mac_trusted(True)       # macOS: shows the Accessibility permission prompt once
        self._stop = False
        threading.Thread(target=self._device_loop, daemon=True).start()
        threading.Thread(target=self._window_loop, daemon=True).start()

    # -------------------------------------------------- config
    def _load(self):
        try:
            with open(paths.CONFIG, encoding="utf-8") as f:
                c = json.load(f)
            base = default_config()
            for k, v in base.items():
                c.setdefault(k, v)
            return c
        except Exception:
            c = default_config()
            self._write(c)
            return c

    def _write(self, c):
        tmp = paths.CONFIG + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(c, f, indent=2, ensure_ascii=False)
        os.replace(tmp, paths.CONFIG)

    def save(self):
        with self.lock:
            self._write(self.cfg)

    def replace_config(self, c):
        with self.lock:
            self.cfg = c
            if self.profile not in c["profiles"]:
                self.profile = next(iter(c["profiles"]))
            self.cfg["active_profile"] = self.profile
            if self.page not in c["profiles"][self.profile]["pages"]:
                self.page = None
            self.save()
        self.redraw()

    # -------------------------------------------------- plugins / templates
    def load_plugins(self):
        self.plugin_errors = []
        from . import actions  # noqa: F401  (registers builtins)
        sys.modules.setdefault("deckcontrol", sys.modules.get("deckcontrol"))
        for f in sorted(glob.glob(os.path.join(paths.PLUGINS, "*.py"))):
            if os.path.basename(f).startswith("_"):
                continue
            try:
                name = "dcplugin_" + os.path.splitext(os.path.basename(f))[0]
                spec = importlib.util.spec_from_file_location(name, f)
                m = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(m)
            except Exception:
                self.plugin_errors.append(os.path.basename(f) + ": " + traceback.format_exc(limit=2))

    def templates(self):
        out = []
        for f in sorted(glob.glob(os.path.join(paths.TEMPLATES, "*.json"))):
            try:
                with open(f, encoding="utf-8") as fh:
                    d = json.load(fh)
                items = d if isinstance(d, list) else [d]
                for t in items:
                    t["_file"] = os.path.basename(f)
                    out.append(t)
            except Exception:
                self.plugin_errors.append(os.path.basename(f) + ": invalid template JSON")
        return out

    # -------------------------------------------------- state helpers
    def profile_obj(self):
        return self.cfg["profiles"][self.profile]

    def page_name(self):
        p = self.profile_obj()
        if self.page in p["pages"]:
            return self.page
        order = [n for n in p.get("page_order", []) if n in p["pages"]] or list(p["pages"])
        return order[0]

    def current_page(self):
        return self.profile_obj()["pages"][self.page_name()]

    def goto_page(self, name):
        with self.lock:
            p = self.profile_obj()
            self.page = name if name in p["pages"] else None
        self.redraw()

    def step_page(self, d):
        with self.lock:
            p = self.profile_obj()
            order = [n for n in p.get("page_order", []) if n in p["pages"]] or list(p["pages"])
            i = order.index(self.page_name())
            self.page = order[(i + d) % len(order)]
        self.redraw()

    def set_profile(self, name):
        with self.lock:
            if name not in self.cfg["profiles"]:
                return
            self.profile = name
            self.cfg["active_profile"] = name
            self.page = None
        self.redraw()

    def change_brightness(self, v, relative):
        with self.lock:
            b = self.cfg["brightness"] + v if relative else v
            self.cfg["brightness"] = max(5, min(100, int(b)))
            d = self.deck
        if d:
            try:
                d.set_brightness(self.cfg["brightness"])
            except Exception:
                pass

    # -------------------------------------------------- logging
    def log(self, kind, text):
        with self.lock:
            self.evid += 1
            self.events.append({"id": self.evid, "t": time.strftime("%H:%M:%S"), "kind": kind, "text": text})
            del self.events[:-200]
        if kind in ("error", "device", "plugin"):
            try:
                with open(paths.LOG, "a", encoding="utf-8") as f:
                    f.write("%s [%s] %s\n" % (time.strftime("%Y-%m-%d %H:%M:%S"), kind, text))
            except Exception:
                pass

    # -------------------------------------------------- drawing
    def redraw(self):
        d = self.deck
        if not d or not d.alive:
            return
        try:
            with self.lock:
                page = self.current_page()["controls"]
            for i, k in enumerate(KEYS):
                d.set_key_image(i, render.render_key(page.get(k)), commit=False)
            d.commit()
        except Exception:
            self.log("error", "redraw failed: " + traceback.format_exc(limit=1))

    # -------------------------------------------------- device
    def _device_loop(self):
        while not self._stop:
            if self.deck and self.deck.alive:
                time.sleep(1)
                continue
            if self.deck:
                self.deck.close()
                self.deck = None
                self.status = "Device disconnected"
                self.log("device", "disconnected")
            try:
                found = dev.find_devices()
                if found:
                    d = dev.Deck(found[0], self._raw)
                    self.deck = d
                    self.status = "Connected: " + d.name
                    self.log("device", "connected: " + d.name)
                    d.set_brightness(self.cfg["brightness"])
                    self.redraw()
                else:
                    self.status = "No device found – plug in the controller" if not dev.hid else \
                        ("Waiting for device" )
            except Exception as e:
                self.status = "Cannot open device (is the vendor app still running?): %s" % e
            time.sleep(2)

    def _raw(self, rid, state, raw):
        m = dict(dev.DEFAULT_INPUT_MAP)
        m.update(self.cfg.get("input_map", {}))
        if self.learn and state:
            tgt = self.learn
            self.learn = None
            self.cfg.setdefault("input_map", {})[str(rid)] = tgt
            self.save()
            self.log("learn", "raw id %d ⇒ %s" % (rid, tgt))
            return
        name = m.get(str(rid))
        self.log("raw", "id=%d (0x%02x) %s → %s" % (rid, rid, "down" if state else "up", name or "unmapped"))
        if not name:
            return
        if "." in name:
            ctrl, kind = name.split(".")
            if kind in ("cw", "ccw"):
                self.fire(ctrl, kind)
                return
        else:
            ctrl = name
        self._button(ctrl, state)

    def _button(self, ctrl, down):
        ev = self.current_page()["controls"].get(ctrl, {}).get("events", {})
        has_long = bool(ev.get("long"))
        if down:
            self.down_at[ctrl] = time.time()
            if has_long:
                def t():
                    if ctrl in self.down_at:
                        self.down_at.pop(ctrl, None)
                        self.fire(ctrl, "long")
                tm = threading.Timer(LONG_MS / 1000, t)
                self.timers[ctrl] = tm
                tm.start()
            else:
                self.fire(ctrl, "press")
        else:
            tm = self.timers.pop(ctrl, None)
            if tm:
                tm.cancel()
            if ctrl in self.down_at:
                self.down_at.pop(ctrl)
                if has_long:
                    self.fire(ctrl, "press")
            self.fire(ctrl, "release")

    def fire(self, ctrl, event):
        if self.paused:
            return
        acts = self.current_page()["controls"].get(ctrl, {}).get("events", {}).get(event)
        if not acts:
            return
        self.log("event", "%s.%s" % (ctrl, event))
        threading.Thread(target=self.run_actions, args=(acts, ctrl, event), daemon=True).start()

    def run_actions(self, acts, ctrl="", event="test"):
        ctx = Ctx(self, ctrl, event)
        for a in acts:
            spec = api.REGISTRY.get(a.get("type"))
            if not spec:
                self.log("error", "unknown action: %s" % a.get("type"))
                continue
            p = {x.name: x.default for x in spec["params"]}
            p.update(a.get("params", {}))
            try:
                spec["fn"](ctx, p)
            except Exception as e:
                self.log("error", "%s failed: %s" % (spec["label"], e))
                break

    # -------------------------------------------------- per-app profiles
    def _window_loop(self):
        from . import winfo
        last = None
        while not self._stop:
            time.sleep(1)
            try:
                app = winfo.foreground_app().lower()
            except Exception:
                continue
            if not app or app == last:
                continue
            last = app
            for name, prof in self.cfg["profiles"].items():
                m = [x.strip().lower() for x in prof.get("match", "").split(",") if x.strip()]
                if m and any(x in app for x in m):
                    if name != self.profile:
                        self.set_profile(name)
                    break

    # -------------------------------------------------- UI facing
    def _ax(self):
        from . import actions
        return actions.mac_trusted(False)

    def state(self):
        return {"status": self.status, "profile": self.profile, "page": self.page_name(),
                "brightness": self.cfg["brightness"], "paused": self.paused,
                "plugin_errors": self.plugin_errors, "learn": self.learn,
                "device": bool(self.deck and self.deck.alive),
                "accessibility": self._ax()}
