"""Minimal ctypes binding to the system libhidapi-hidraw (Linux).

The PyPI hidapi wheel uses libusb, which needs root-only USB access.  The hidraw backend
goes through /dev/hidraw*, which desktop udev rules make accessible to the logged-in user.
Exposes just what device.py uses: enumerate() and device().
"""
import ctypes
import ctypes.util


class _Info(ctypes.Structure):
    pass


_Info._fields_ = [
    ("path", ctypes.c_char_p), ("vendor_id", ctypes.c_ushort), ("product_id", ctypes.c_ushort),
    ("serial_number", ctypes.c_wchar_p), ("release_number", ctypes.c_ushort),
    ("manufacturer_string", ctypes.c_wchar_p), ("product_string", ctypes.c_wchar_p),
    ("usage_page", ctypes.c_ushort), ("usage", ctypes.c_ushort), ("interface_number", ctypes.c_int),
    ("next", ctypes.POINTER(_Info)), ("bus_type", ctypes.c_int)]

_lib = None
for _n in ("libhidapi-hidraw.so.0", ctypes.util.find_library("hidapi-hidraw") or ""):
    try:
        _lib = ctypes.CDLL(_n)
        break
    except OSError:
        pass
if _lib is None:
    raise ImportError("libhidapi-hidraw not found")

_lib.hid_enumerate.restype = ctypes.POINTER(_Info)
_lib.hid_enumerate.argtypes = [ctypes.c_ushort, ctypes.c_ushort]
_lib.hid_free_enumeration.argtypes = [ctypes.POINTER(_Info)]
_lib.hid_open_path.restype = ctypes.c_void_p
_lib.hid_open_path.argtypes = [ctypes.c_char_p]
_lib.hid_close.argtypes = [ctypes.c_void_p]
_lib.hid_write.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t]
_lib.hid_read_timeout.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_size_t, ctypes.c_int]


def enumerate(vid=0, pid=0):
    out = []
    head = _lib.hid_enumerate(vid, pid)
    p = head
    while p:
        i = p.contents
        out.append({"path": i.path, "vendor_id": i.vendor_id, "product_id": i.product_id,
                    "usage_page": i.usage_page, "usage": i.usage, "interface_number": i.interface_number})
        p = i.next
    if head:
        _lib.hid_free_enumeration(head)
    return out


class device:
    def __init__(self):
        self._h = None

    def open_path(self, path):
        h = _lib.hid_open_path(path)
        if not h:
            raise IOError("open failed")
        self._h = h

    def write(self, data):
        n = _lib.hid_write(self._h, bytes(data), len(data))
        if n < 0:
            raise IOError("write failed")
        return n

    def read(self, size, timeout_ms=0):
        buf = ctypes.create_string_buffer(size)
        n = _lib.hid_read_timeout(self._h, buf, size, timeout_ms)
        if n < 0:
            raise IOError("read failed")
        return list(buf.raw[:n])

    def close(self):
        if self._h:
            _lib.hid_close(self._h)
            self._h = None
