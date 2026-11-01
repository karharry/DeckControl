"""Virtual keyboard through /dev/uinput (Linux).

pynput's X11 backend only reaches XWayland windows, so on a Wayland desktop shortcuts such as
ctrl+c would be ignored by native apps.  uinput events work everywhere.  Shortcuts and media
keys use physical key positions, so they are layout independent.  Needs write access to
/dev/uinput (granted to the logged-in user by the usual udev ACL).
"""
import fcntl
import os
import struct
import time

CODES = {
    "esc": 1, "backspace": 14, "tab": 15, "enter": 28, "ctrl": 29, "ctrl_l": 29, "shift": 42, "shift_l": 42,
    "shift_r": 54, "alt": 56, "alt_l": 56, "alt_r": 100, "alt_gr": 100, "ctrl_r": 97, "space": 57,
    "caps_lock": 58, "cmd": 125, "cmd_l": 125, "cmd_r": 126, "menu": 127, "insert": 110, "delete": 111,
    "home": 102, "end": 107, "page_up": 104, "page_down": 109, "up": 103, "down": 108, "left": 105,
    "right": 106, "print_screen": 99, "scroll_lock": 70, "pause": 119, "num_lock": 69,
    "media_play_pause": 164, "media_next": 163, "media_previous": 165,
    "media_volume_up": 115, "media_volume_down": 114, "media_volume_mute": 113,
}
CODES.update({"f%d" % i: c for i, c in enumerate(list(range(59, 69)) + [87, 88], 1)})
CODES.update({"f%d" % (13 + i): 183 + i for i in range(12)})
_ROW = {"q": 16, "w": 17, "e": 18, "r": 19, "t": 20, "y": 21, "u": 22, "i": 23, "o": 24, "p": 25,
        "a": 30, "s": 31, "d": 32, "f": 33, "g": 34, "h": 35, "j": 36, "k": 37, "l": 38,
        "z": 44, "x": 45, "c": 46, "v": 47, "b": 48, "n": 49, "m": 50}
CODES.update(_ROW)
CODES.update({str(d): c for d, c in zip("1234567890", range(2, 12))})
CODES.update({"-": 12, "=": 13, "[": 26, "]": 27, ";": 39, "'": 40, "`": 41, "\\": 43, ",": 51, ".": 52, "/": 53,
              "+": 13})


def _code(k):
    if isinstance(k, str):
        return CODES.get(k.lower())
    return CODES.get(getattr(k, "name", None))


class Keyboard:
    def __init__(self):
        self.fd = os.open("/dev/uinput", os.O_WRONLY | os.O_NONBLOCK)
        fcntl.ioctl(self.fd, 0x40045564, 1)  # UI_SET_EVBIT EV_KEY
        for c in set(CODES.values()):
            fcntl.ioctl(self.fd, 0x40045565, c)
        fcntl.ioctl(self.fd, 0x405c5503, struct.pack("<HHHH80sI", 3, 0x1209, 0xdec0, 1, b"DeckControl keyboard", 0))
        fcntl.ioctl(self.fd, 0x5501)  # UI_DEV_CREATE
        time.sleep(0.3)  # let the desktop notice the new device

    def _emit(self, code, value):
        os.write(self.fd, struct.pack("<qqHHi", 0, 0, 1, code, value))
        os.write(self.fd, struct.pack("<qqHHi", 0, 0, 0, 0, 0))

    def supports(self, k):
        return _code(k) is not None

    def press(self, k):
        self._emit(_code(k), 1)

    def release(self, k):
        self._emit(_code(k), 0)
