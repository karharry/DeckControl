"""Name of the foreground application (for per-app profiles)."""
import subprocess
import sys


def foreground_app():
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes
        u = ctypes.windll.user32
        k = ctypes.windll.kernel32
        h = u.GetForegroundWindow()
        pid = wintypes.DWORD()
        u.GetWindowThreadProcessId(h, ctypes.byref(pid))
        k.OpenProcess.restype = wintypes.HANDLE
        ph = k.OpenProcess(0x1000, False, pid.value)
        if not ph:
            return ""
        buf = ctypes.create_unicode_buffer(520)
        n = wintypes.DWORD(520)
        k.QueryFullProcessImageNameW(ph, 0, buf, ctypes.byref(n))
        k.CloseHandle(ph)
        return buf.value.replace("\\", "/").split("/")[-1]
    if sys.platform == "darwin":
        r = subprocess.run(["osascript", "-e",
                            'tell application "System Events" to get name of first process whose frontmost is true'],
                           capture_output=True, text=True, timeout=2)
        return r.stdout.strip()
    return ""
