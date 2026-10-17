"""Low-level HID driver for the Ajazz AKP03 family (and Mirabox N3 clones).

Protocol (reverse engineered by the open source "mirajazz" project):
  * every command is an output report: 0x00, "CRT", 0x00, 0x00, <CMD>, args... zero padded
  * images are JPEGs sent with a BAT header followed by raw chunks, committed with STP
  * input reports start with "ACK"; byte 9 = control id, byte 10 = state (v3 devices)
"""
import io
import threading
import time

try:
    import hid
except Exception as e:  # pragma: no cover
    hid = None
    HID_ERROR = str(e)
else:
    HID_ERROR = ""

from PIL import Image

AJAZZ = 0x0300
# (vid, pid) -> (name, protocol_version)
KNOWN = {
    (0x0300, 0x1001): ("Ajazz AKP03", 2),
    (0x0300, 0x1002): ("Ajazz AKP03E", 2),
    (0x0300, 0x1003): ("Ajazz AKP03R", 2),
    (0x0300, 0x3002): ("Ajazz AKP03E (rev 2)", 3),
    (0x0300, 0x3003): ("Ajazz AKP03R (rev 2)", 3),
    (0x6602, 0x1000): ("Mirabox N3", 2),
    (0x6602, 0x1002): ("Mirabox N3", 2),
    (0x6603, 0x1002): ("Mirabox N3", 3),
    (0x6603, 0x1003): ("Mirabox N3", 3),
    (0x1500, 0x3001): ("Soomfon SE", 3),
    (0x5548, 0x1001): ("TreasLin N3", 3),
}
USAGE_PAGE = 65440

# raw input id -> logical control id.  Overridable from the config ("input_map").
DEFAULT_INPUT_MAP = {
    "1": "k1", "2": "k2", "3": "k3", "4": "k4", "5": "k5", "6": "k6",
    "37": "b7", "48": "b8", "49": "b9",           # 0x25 0x30 0x31
    "51": "e1.press", "53": "e2.press", "52": "e3.press",   # 0x33 0x35 0x34
    "144": "e1.ccw", "145": "e1.cw",              # 0x90 0x91
    "80": "e2.ccw", "81": "e2.cw",                # 0x50 0x51
    "96": "e3.ccw", "97": "e3.cw",                # 0x60 0x61
}


def find_devices():
    if hid is None:
        return []
    out = []
    for d in hid.enumerate():
        key = (d["vendor_id"], d["product_id"])
        if key in KNOWN and d.get("usage_page") == USAGE_PAGE:
            out.append(d)
    return out


class Deck:
    """Connection to one controller.  Thread safe for writes."""

    def __init__(self, info, on_raw):
        self.info = info
        self.name, self.proto = KNOWN[(info["vendor_id"], info["product_id"])]
        self.packet = 1024 if self.proto >= 2 else 512
        # rev2 / v3 firmware wants 64x64 rotated 90deg, older wants 60x60 unrotated
        self.img_size, self.img_rot = ((64, 64), 90) if self.proto >= 3 else ((60, 60), 0)
        self.h = hid.device()
        self.h.open_path(info["path"])
        self.lock = threading.Lock()
        self.on_raw = on_raw
        self.alive = True
        self._toggle = {}
        self._send(b"CRT\0\0DIS")
        self._send(b"CRT\0\0LIG\0\0\x32\x32")
        self.clear_all()          # wipe factory / previous-app images that could show around ours
        time.sleep(0.3)
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        self._ka = threading.Thread(target=self._keepalive, daemon=True)
        self._ka.start()

    # -- low level -------------------------------------------------
    def _send(self, payload: bytes):
        with self.lock:
            self.h.write(b"\x00" + payload.ljust(self.packet, b"\0"))

    def _keepalive(self):
        while self.alive:
            time.sleep(10)
            try:
                self._send(b"CRT\0\0CONNECT")
            except Exception:
                return

    def _read_loop(self):
        while self.alive:
            try:
                data = self.h.read(512, 200)
            except Exception:
                self.alive = False
                return
            if not data or bytes(data[:3]) != b"ACK":
                continue
            rid = data[9]
            state = data[10] if self.proto >= 3 else None
            if state is None:  # v2: no state byte, device sends press and release reports
                st = not self._toggle.get(rid, False)
                self._toggle[rid] = st
                state = 1 if st else 0
            try:
                self.on_raw(rid, bool(state), bytes(data[:16]))
            except Exception:
                pass

    # -- public ----------------------------------------------------
    def set_brightness(self, pct):
        pct = max(0, min(100, int(pct)))
        self._send(b"CRT\0\0LIG\0\0" + bytes([pct, pct]))

    def set_key_image(self, key, img: Image.Image, commit=True):
        """key = 0..5 ; img any size PIL image."""
        im = img.convert("RGB").resize(self.img_size, Image.LANCZOS)
        if self.img_rot:
            im = im.rotate(-self.img_rot)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=92)
        data = buf.getvalue()
        self._send(b"CRT\0\0BAT\0\0" + bytes([len(data) >> 8, len(data) & 255, key + 1]))
        for i in range(0, len(data), self.packet):
            self._send(data[i:i + self.packet])
        if commit:
            self.commit()

    def commit(self):
        self._send(b"CRT\0\0STP")

    def clear_all(self):
        self._send(b"CRT\0\0CLE\0\0\0\xff")
        self.commit()

    def close(self):
        self.alive = False
        try:
            self.h.close()
        except Exception:
            pass
