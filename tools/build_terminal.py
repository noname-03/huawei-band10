"""Build the band10-terminal watchface for Huawei Band 10 (HWHD07, 194x368).

Format reversed from the Band 8/10 lineage:
  com.huawei.watchface = <BBHHHII header><proto><fat><resources>
  resources = "UUUU\\x01\\x00\\x00\\x01" + RLE-encoded BGRA images
"""

import io
import json
import math
import struct
import zipfile
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist"
BUILD = ROOT / "build"
S = 3
W, H = 194, 368

C = {
    "bg": "#0A0E13",
    "text": "#E6EDF3",
    "dim": "#5C6B7C",
    "green": "#3DDC97",
    "cyan": "#59C2FF",
    "red": "#FF5C7A",
    "rule": "#1B2531",
}

FONTS = Path("C:/Windows/Fonts")
BIG_CELL, MED_CELL, WD_CELL, MO_CELL = (34, 56), (15, 26), (24, 14), (24, 14)
BLANK_CELL, SIGN_CELL = (10, 26), (10, 26)

BIG_FONT = ImageFont.truetype(str(FONTS / "consolab.ttf"), 54 * S)
MED_FONT = ImageFont.truetype(str(FONTS / "consolab.ttf"), 22 * S)
LABEL_FONT = ImageFont.truetype(str(FONTS / "consola.ttf"), 11 * S)
SMALL = ImageFont.truetype(str(FONTS / "consola.ttf"), 9 * S)
TINY = ImageFont.truetype(str(FONTS / "consola.ttf"), 8 * S)
MICRO = ImageFont.truetype(str(FONTS / "consola.ttf"), 7.5 * S)

POS = {
    "hour10": (22, 54), "hour1": (56, 54),
    "min10": (104, 54), "min1": (138, 54),
    "weekday": (13, 123), "day": (47, 117), "month": (86, 123),
    "steps": (12, 172), "heart": (30, 230),
}

RLE = bytes([137, 103, 69, 35])
MARK = bytes([69, 35, 136, 136])
RES_PREFIX = b"UUUU\x01\x00\x00\x01"


def cell(size, paint):
    im = Image.new("RGBA", (size[0] * S, size[1] * S), (0, 0, 0, 0))
    paint(ImageDraw.Draw(im))
    return im.resize(size, Image.LANCZOS)


def glyph(size, text, font, fill):
    def paint(d):
        d.text((size[0] * S // 2, size[1] * S // 2), text, font=font, fill=fill, anchor="mm")
    return cell(size, paint)


def background(diag=False):
    if diag:
        im = Image.new("RGBA", (W * S, H * S), "#FF00FF")
        d = ImageDraw.Draw(im)
        d.text((W * S // 2, H * S // 2), "DIAG",
               font=ImageFont.truetype(str(FONTS / "consolab.ttf"), 40 * S),
               fill="#FFFFFF", anchor="mm")
        return im.resize((W, H), Image.LANCZOS)

    im = Image.new("RGBA", (W * S, H * S), C["bg"])
    d = ImageDraw.Draw(im, "RGBA")

    def t(xy, s, font, fill, anchor="lt"):
        d.text((xy[0] * S, xy[1] * S), s, font=font, fill=fill, anchor=anchor)

    def rule(y):
        d.line([(12 * S, y * S), (182 * S, y * S)], fill=C["rule"], width=S)

    def spaced(xy, s, font, fill, tracking):
        x, y = xy
        for ch in s:
            d.text((x * S, y * S), ch, font=font, fill=fill, anchor="lt")
            x += d.textlength(ch, font=font) / S + tracking

    t((12, 13), "~/band10", SMALL, C["dim"])
    t((182, 13), "tty0", SMALL, C["dim"], anchor="rt")
    t((12, 45), "$ date +%H:%M", TINY, C["dim"])
    for dot in (72, 90):
        d.rounded_rectangle([92 * S, dot * S, 99 * S, (dot + 7) * S],
                            radius=2 * S, fill=C["green"])
    t((182, 122), "2026", LABEL_FONT, C["dim"], anchor="rt")

    rule(148)
    spaced((12, 160), "STEPS", MICRO, C["dim"], 1.6)
    t((182, 186), "/ 10k", SMALL, C["dim"], anchor="rt")

    d.line([(12 * S, 204 * S), (182 * S, 204 * S)], fill=C["rule"], width=S)
    for x in range(12, 183, 17):
        d.line([(x * S, 204 * S), (x * S, 209 * S)], fill=C["rule"], width=S)
    d.line([(12 * S, 209 * S), (182 * S, 209 * S)], fill=C["rule"], width=S)

    spaced((12, 222), "HEART", MICRO, C["dim"], 1.6)
    heart(d, 18, 243, 10.5, C["red"])
    t((80, 243), "bpm", SMALL, C["dim"])
    spark(d, (112, 228, 182, 252))

    rule(268)
    t((12, 280), "$ git status", TINY, C["dim"])
    t((182, 280), "clean", TINY, C["green"], anchor="rt")

    rule(312)
    t((97, 322), "band10-terminal v1.0", MICRO, C["dim"], anchor="mt")

    return im.resize((W, H), Image.LANCZOS)


def heart(d, cx, cy, size, fill):
    pts = []
    for i in range(160):
        a = 2 * math.pi * i / 160
        hx = 16 * math.sin(a) ** 3
        hy = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx * S + hx * size * S / 32, cy * S + hy * size * S / 32))
    d.polygon(pts, fill=fill)


def spark(d, box):
    x0, y0, x1, y1 = box
    values = [70, 74, 71, 78, 84, 79, 76, 73, 71, 75, 72, 72]
    lo, hi = min(values) - 3, max(values) + 3
    pts = []
    for i, v in enumerate(values):
        px = x0 + (x1 - x0) * i / (len(values) - 1)
        py = y1 - (y1 - y0) * (v - lo) / (hi - lo)
        pts.append((px * S, py * S))
    d.line(pts, fill=C["red"], width=S, joint="curve")
    d.ellipse([pts[-1][0] - 2 * S, pts[-1][1] - 2 * S,
               pts[-1][0] + 2 * S, pts[-1][1] + 2 * S], fill=C["red"])


WEEKDAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
          "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]


def build_resources(diag=False):
    res = {2: background(diag)}
    if diag:
        return res
    for n in range(10):
        res[3 + n] = glyph(BIG_CELL, str(n), BIG_FONT, C["green"])
        res[13 + n] = glyph(MED_CELL, str(n), MED_FONT, C["text"])
    for n, name in enumerate(WEEKDAYS):
        res[23 + n] = glyph(WD_CELL, name, LABEL_FONT, C["cyan"])
    for n, name in enumerate(MONTHS):
        res[30 + n] = glyph(MO_CELL, name, LABEL_FONT, C["dim"])
    for n in range(42, 53):
        res[n] = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    res[53] = Image.new("RGBA", BLANK_CELL, (0, 0, 0, 0))
    res[54] = glyph(SIGN_CELL, "-", MED_FONT, C["text"])
    return res


def encode_image(im):
    im = im.convert("RGBA")
    raw = im.tobytes()
    px = [(raw[i + 2], raw[i + 1], raw[i], raw[i + 3]) for i in range(0, len(raw), 4)]
    out = bytearray(MARK + struct.pack("<HH", im.width, im.height))
    i = 0
    while i < len(px):
        p = px[i]
        j = i + 1
        while j < len(px) and px[j] == p:
            j += 1
        n = j - i
        if n > 3 or bytes(p) == RLE:
            out += RLE + bytes(p) + struct.pack("<I", n)
        else:
            out += bytes(p) * n
        i = j
    return bytes(out)


def pack_resources(res):
    encoded = [encode_image(Image.new("RGBA", (1, 1), (0, 0, 0, 0)))]
    encoded += [encode_image(res[n]) for n in sorted(res)]
    fat = bytearray()
    offset = len(RES_PREFIX)
    for blob in encoded:
        fat += struct.pack("<II", offset, len(blob))
        offset += len(blob)
    return bytes(fat), RES_PREFIX + b"".join(encoded)


def varint(n):
    out = bytearray()
    while True:
        b = n & 0x7F
        n >>= 7
        out.append(b | 0x80 if n else b)
        if not n:
            return bytes(out)


def fv(field, value):
    return varint(field << 3) + varint(value)


def fb(field, value):
    if isinstance(value, str):
        value = value.encode()
    return varint((field << 3) | 2) + varint(len(value)) + value


def position(x, y):
    return fv(1, x) + fv(2, y)


def layer_single(index, name, x, y):
    return fv(1, index) + fv(2, 1) + fb(4, fb(1, name) + fb(2, position(x, y)))


def layer_selected(index, value_type, names, x, y):
    body = b"".join(fb(1, n) for n in names) + fb(2, position(x, y)) + fv(3, value_type)
    return fv(1, index) + fv(2, 2) + fb(5, body)


def layer_combined(index, value_type, x, y, align=0, signed=False):
    body = (b"".join(fb(1, f"{n:03}") for n in range(13, 23))
            + fb(2, "013") + fb(2, "053")
            + fb(3, position(x, y)) + fv(4, align) + fv(5, value_type))
    if signed:
        body += fb(6, "054")
    return fv(1, index) + fv(2, 3) + fb(6, body)


def container(index, data_type, layers):
    rect = fv(1, 0) + fv(2, 0) + fv(3, W) + fv(4, H)
    return (fv(1, index) + fv(2, 0) + fb(5, rect)
            + b"".join(fb(6, layer) for layer in layers) + fv(8, data_type))


def element(label, layers=None, containers=None):
    out = fv(1, label) + fv(2, 0)
    out += b"".join(fb(5, layer) for layer in (layers or []))
    out += b"".join(fb(8, c) for c in (containers or []))
    return out


def encode_proto(diag=False):
    proto = fb(1, element(0, [layer_single(0, "002", 0, 0)]))
    if diag:
        return proto + fb(2, "band10-diag") + fb(3, "band10-diag") + fb(4, f"{W}x{H}")

    big = [f"{n:03}" for n in range(3, 13)]
    time_layers = [
        layer_selected(0, 59, big[:3], *POS["hour10"]),
        layer_selected(1, 60, big, *POS["hour1"]),
        layer_selected(2, 61, big[:6], *POS["min10"]),
        layer_selected(3, 62, big, *POS["min1"]),
    ]
    date_layers = [
        layer_selected(0, 52, [f"{n:03}" for n in range(23, 30)], *POS["weekday"]),
        layer_combined(1, 17, *POS["day"]),
        layer_selected(2, 51, [f"{n:03}" for n in range(30, 42)], *POS["month"]),
    ]
    steps = container(0, 10, [layer_combined(0, 0, *POS["steps"], align=0)])
    pulse = container(1, 11, [layer_combined(0, 2, *POS["heart"], align=0)])

    proto = fb(1, element(0, [layer_single(0, "002", 0, 0)]))
    proto += fb(1, element(1, time_layers))
    proto += fb(1, element(2, date_layers))
    proto += fb(1, element(3, containers=[steps, pulse]))
    proto += fb(2, "band10-terminal") + fb(3, "band10-terminal") + fb(4, f"{W}x{H}")
    return proto

def assemble(proto, fat, resources):
    header = struct.pack("<BBHHHII", 2, 0, len(proto), len(fat), 0, len(resources), 0)
    return header + proto + fat + resources


DESCRIPTION = """<?xml version="1.0" encoding="UTF-8"?>
<HwTheme>
  <title>band10-terminal</title>
  <title-cn>band10-terminal</title-cn>
  <author>fahru</author>
  <designer>fahru</designer>
  <screen>HWHD07</screen>
  <version>1.0.0</version>
  <font>Default</font>
  <font-cn>Default</font-cn>
</HwTheme>
"""


def preview(res, path, diag=False):
    im = res[2].copy()
    if diag:
        im.convert("RGB").save(path, quality=95)
        return im

    def put(n, xy):
        im.alpha_composite(res[n], xy)
    put(3, POS["hour10"]); put(12, POS["hour1"])
    put(3, POS["min10"]); put(4, POS["min1"])
    put(26, POS["weekday"])
    put(16, POS["day"]); put(17, (POS["day"][0] + 15, POS["day"][1]))
    put(39, POS["month"])
    for i, ch in enumerate("8432"):
        put(13 + int(ch), (POS["steps"][0] + i * 15, POS["steps"][1]))
    put(20, POS["heart"]); put(15, (POS["heart"][0] + 15, POS["heart"][1]))
    im.convert("RGB").save(path, quality=95)
    return im


def selftest(blob, resources, proto):
    assert proto[0] == 0x0A, "proto must start with a wrapped element (field 1)"
    ver, zero, proto_len, fat_len, pad, res_len, tail = struct.unpack("<BBHHHII", blob[:16])
    assert ver == 2 and zero == 0 and pad == 0 and tail == 0
    assert 16 + proto_len + fat_len + res_len == len(blob), "length mismatch"
    assert proto_len == len(proto) and blob[16:16 + proto_len] == proto
    assert blob[16 + proto_len + fat_len:][:8] == RES_PREFIX
    assert fat_len // 8 == len(resources) + 1, "fat count mismatch"
    offset = 8
    for i in range(fat_len // 8):
        off, ln = struct.unpack("<II", blob[16 + proto_len + i * 8:16 + proto_len + i * 8 + 8])
        assert off == offset and ln > 0, f"fat {i} bad"
        offset += ln
    assert offset == res_len, "resource blob length mismatch"
    return True


def payload_zip(blob, res, name):
    info = f"""<?xml version="1.0" encoding="UTF-8"?>
<HwTheme><title>{name}</title><title-cn>{name}</title-cn>
<author>fahru</author><designer>fahru</designer><screen>HWHD07</screen>
<version>1.0.0</version><font>Default</font><font-cn>Default</font-cn></HwTheme>"""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("watchface.bin", blob)
        zf.writestr("watchface/watch_face_info.xml", info)
        for n in sorted(res):
            png = io.BytesIO()
            res[n].save(png, "PNG")
            zf.writestr(f"watchface/res/A100_{n:03}.png", png.getvalue())
    return buf.getvalue()


def main(diag=False, as_zip=False):
    name = "band10-diag" if diag else "band10-terminal"
    if as_zip:
        name += "-zip"
    DIST.mkdir(exist_ok=True)
    BUILD.mkdir(exist_ok=True)
    res = build_resources(diag)
    proto = encode_proto(diag)
    fat, resources = pack_resources(res)
    blob = assemble(proto, fat, resources)
    selftest(blob, res, proto)
    payload = payload_zip(blob, res, name) if as_zip else blob

    cover = preview(res, DIST / f"{name}-preview.png", diag)
    (BUILD / "com.huawei.watchface").write_bytes(blob)
    cover.convert("RGB").save(BUILD / "cover.jpg", quality=92)
    cover.convert("RGB").resize((97, 184), Image.LANCZOS).save(BUILD / "icon_small.jpg", quality=90)

    out = DIST / f"{name}.hwt"
    with zipfile.ZipFile(out, "w") as zf:
        for entry, data in (
            ("com.huawei.watchface", payload),
            ("description.xml", DESCRIPTION.replace("band10-terminal", name).encode()),
            ("preview/cover.jpg", (BUILD / "cover.jpg").read_bytes()),
            ("preview/icon_small.jpg", (BUILD / "icon_small.jpg").read_bytes()),
        ):
            info = zipfile.ZipInfo(entry, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)

    print(f"resources={len(res)} proto={len(proto)}B fat={len(fat)}B res={len(resources)}B")
    print(f"hwt={out} size={out.stat().st_size}")


if __name__ == "__main__":
    argv = __import__("sys").argv[1:]
    main("--diag" in argv, "--zip" in argv)
