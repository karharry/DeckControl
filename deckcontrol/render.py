"""Draws the picture shown on each display key."""
import os
import sys

from PIL import Image, ImageDraw, ImageFont

from . import paths

S = 192  # render size, downscaled by the driver

_font_cache = {}


def _font_files(emoji=False):
    if sys.platform == "win32":
        w = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
        return [os.path.join(w, "seguiemj.ttf")] if emoji else [os.path.join(w, "segoeuib.ttf"), os.path.join(w, "arialbd.ttf")]
    if sys.platform == "darwin":
        return (["/System/Library/Fonts/Apple Color Emoji.ttc"] if emoji else
                ["/System/Library/Fonts/Helvetica.ttc", "/System/Library/Fonts/SFNS.ttf"])
    return (["/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf"] if emoji else
            ["/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"])


def font(size, emoji=False):
    k = (size, emoji)
    if k in _font_cache:
        return _font_cache[k]
    f = None
    sizes = ([160, 109, 137, 128, 96, 64, 48, 32] if sys.platform != "win32" else [size]) if emoji else [size]
    for p in _font_files(emoji):
        for sz in sizes:
            try:
                f = ImageFont.truetype(p, sz)
                if emoji:
                    ImageDraw.Draw(Image.new("RGBA", (300, 300))).text((0, 0), "⭐", font=f, embedded_color=True)
                break
            except Exception:
                f = None
        if f:
            break
    if f is None and not emoji:
        try:
            f = ImageFont.load_default(size)
        except Exception:
            f = ImageFont.load_default()
    _font_cache[k] = f
    return f


def _is_emoji(s):
    return bool(s) and any(ord(c) > 0x2000 for c in s)


def render_key(ctrl, active=False):
    """ctrl = {label, icon, bg, fg, image}. Returns RGB PIL image."""
    ctrl = ctrl or {}
    bg = ctrl.get("bg") or "#1b1f2a"
    fg = ctrl.get("fg") or "#ffffff"
    im = Image.new("RGB", (S, S), bg)
    img_path = ctrl.get("image")
    if img_path:
        p = img_path if os.path.isabs(img_path) else os.path.join(paths.IMAGES, img_path)
        try:
            pic = Image.open(p).convert("RGBA")
            fit = ctrl.get("fit") or "fit"
            if fit == "stretch":
                pic = pic.resize((S, S), Image.LANCZOS)
            elif fit == "fill":
                sc = S / min(pic.size)
                pic = pic.resize((max(S, round(pic.width * sc)), max(S, round(pic.height * sc))), Image.LANCZOS)
                pic = pic.crop(((pic.width - S) // 2, (pic.height - S) // 2, (pic.width + S) // 2, (pic.height + S) // 2))
            else:
                pic.thumbnail((S, S), Image.LANCZOS)
            im.paste(pic, ((S - pic.width) // 2, (S - pic.height) // 2), pic)
        except Exception:
            pass
    d = ImageDraw.Draw(im)
    icon = (ctrl.get("icon") or "").strip()
    label = (ctrl.get("label") or "").strip()
    top = 0
    if icon and not img_path:
        if _is_emoji(icon):
            f = font(110, True)
            try:
                if f is None:
                    raise RuntimeError("no emoji font")
                tmp = Image.new("RGBA", (320, 320), (0, 0, 0, 0))
                ImageDraw.Draw(tmp).text((0, 0), icon[:2], font=f, embedded_color=True)
                bb = tmp.getbbox()
                if bb:
                    tmp = tmp.crop(bb)
                    target = 100 if label else 130
                    sc = target / max(tmp.size)
                    tmp = tmp.resize((max(1, int(tmp.width * sc)), max(1, int(tmp.height * sc))), Image.LANCZOS)
                    y = 14 if label else (S - tmp.height) // 2
                    im.paste(tmp, ((S - tmp.width) // 2, y), tmp)
                    top = y + tmp.height
            except Exception:
                d.text((S // 2, 60), icon, fill=fg, font=font(70), anchor="mm")
        else:
            size = 100 if len(icon) <= 2 else 60
            d.text((S // 2, 70 if label else S // 2), icon, fill=fg, font=font(size), anchor="mm")
    if label:
        lines = label.split("\n")[:2]
        size = 34 if len(lines) == 1 else 28
        f = font(size)
        while size > 14 and max(d.textlength(l, font=f) for l in lines) > S - 12:
            size -= 2
            f = font(size)
        total = size * len(lines) * 1.15
        y = S - 10 - total if (icon or img_path) else (S - total) / 2
        for i, l in enumerate(lines):
            d.text((S // 2, y + size * 1.15 * i + size / 2), l, fill=fg, font=f, anchor="mm")
    if active:
        d.rectangle([0, 0, S - 1, S - 1], outline="#ffcc33", width=8)
    return im
