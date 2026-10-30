"""Generate design variants of the Band 10 watchface (HWHD07, 194x368)."""

import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from build_terminal import (
    assemble, container, element, fb, fv, layer_combined, layer_selected,
    layer_single, pack_resources, payload_zip, selftest, W, H,
)

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "variants"
S = 3
FONTS = Path("C:/Windows/Fonts")

VARIANTS = [
    dict(slug="paper", title="Paper Terminal", mode="solid", bg="#F4F1E8",
         time="#0F7B5F", ink="#1A1E24", dim="#8C8578", accent="#0F7B5F",
         font="consolab.ttf", size=58, header="~/band10", footer="paper v1",
         deco="rule"),
    dict(slug="snow", title="Mono Contrast", mode="solid", bg="#FFFFFF",
         time="#000000", ink="#000000", dim="#9AA0A6", accent="#E5342A",
         font="consolab.ttf", size=62, header="mono", footer="high contrast",
         deco="rule"),
    dict(slug="nord", title="Nord Light", mode="solid", bg="#ECEFF4",
         time="#2E3440", ink="#2E3440", dim="#8A94A6", accent="#5E81AC",
         font="segoeuib.ttf", size=60, header="nord", footer="nord v1",
         deco="rule"),
    dict(slug="blueprint", title="Blueprint", mode="grid", bg="#E9F2F8",
         time="#0B3A5B", ink="#0B3A5B", dim="#7FA6C0", accent="#0B6FA4",
         font="bahnschrift.ttf", size=60, header="draft/01", footer="scale 1:1",
         deco="grid"),
    dict(slug="sunrise", title="Sunrise", mode="vgrad", bg="#FFD9A8",
         bg2="#FFB3C7", time="#5B2333", ink="#5B2333", dim="#A2717F",
         accent="#E4572E", font="segoeuib.ttf", size=60, header="dawn",
         footer="rise 06:12", deco="rule"),
    dict(slug="vapor", title="Lavender", mode="vgrad", bg="#F3E7FF",
         bg2="#D9C2FF", time="#4A148C", ink="#311B92", dim="#8E7DB0",
         accent="#E91E63", font="consolab.ttf", size=58, header="vapor",
         footer="aesthetic", deco="dots"),
    dict(slug="amber", title="Amber CRT", mode="scan", bg="#120C05",
         time="#FFB000", ink="#FFD48A", dim="#8A6A3A", accent="#FF6B00",
         font="consolab.ttf", size=60, header="tty0", footer="crt v1",
         deco="scan"),
    dict(slug="mint", title="Neon Mint", mode="solid", bg="#06110D",
         time="#4DFFC3", ink="#EAFFF7", dim="#4C7A6B", accent="#4DFFC3",
         font="consolab.ttf", size=62, header="~/mint", footer="neon v1",
         deco="rule"),
    dict(slug="carbon", title="Carbon", mode="solid", bg="#1B1F24",
         time="#FFFFFF", ink="#E8EAED", dim="#8A9199", accent="#FF9F0A",
         font="bahnschrift.ttf", size=62, header="", footer="putri", love=True,
         deco="rule"),
    dict(slug="carbon-new", title="Carbon New", mode="solid", bg="#1B1F24",
         time="#FFFFFF", ink="#E8EAED", dim="#8A9199", accent="#FF9F0A",
         font="bahnschrift.ttf", size=64, header="", footer="putri", love=True,
         love_color="#FF3B30", deco="rule"),
    dict(slug="matrix", title="Matrix Green", mode="solid", bg="#000000",
         time="#33FF66", ink="#B9FFCB", dim="#2F7A46", accent="#33FF66",
         font="consolab.ttf", size=60, header="root@band", footer="matrix",
         deco="rule"),
]


def fnt(name, size):
    return ImageFont.truetype(str(FONTS / name), int(round(size * S)))


def metrics(size, font_name):
    adv = ImageFont.truetype(str(FONTS / font_name), int(size)).getlength("0")
    cw = math.ceil(adv) + 3
    ch = math.ceil(size * 1.08)
    colon = max(6, round(cw * 0.40))
    span = cw * 4 + colon
    assert span <= 180, f"clock too wide: {span}"
    return cw, ch, colon, span


def layout(spec):
    cw, ch, colon, span = metrics(spec["size"], spec["font"])
    x = (W - span) // 2
    y = spec.get("time_y", 40)
    med = spec.get("med_size", 26)
    mw = math.ceil(med * 0.62)
    mh = math.ceil(med * 1.08)
    date_y = y + ch + 10
    wd_w, mo_w, gap = 34, 32, 6
    total = wd_w + gap + mw * 2 + gap + mo_w
    dx = (W - total) // 2
    date_pos = {
        "weekday": (dx, date_y + (mh - 15) // 2),
        "day": (dx + wd_w + gap, date_y),
        "month": (dx + wd_w + gap + mw * 2 + gap, date_y + (mh - 15) // 2),
    }
    rule1 = date_y + mh + 12
    steps_label = rule1 + 10
    steps_y = steps_label + 11
    hr_label = steps_y + mh + 26
    hr_y = hr_label + 11
    return {
        "cw": cw, "ch": ch, "colon": colon,
        "h10": (x, y), "h1": (x + cw, y),
        "colon_pos": (x + 2 * cw, y),
        "m10": (x + 2 * cw + colon, y), "m1": (x + 3 * cw + colon, y),
        "mw": mw, "mh": mh, "med": med,
        "date_y": date_y, "date_pos": date_pos, "rule1": rule1,
        "steps_label": steps_label, "steps_y": steps_y,
        "hr_label": hr_label, "hr_y": hr_y,
    }


def backdrop(spec):
    im = Image.new("RGBA", (W * S, H * S), spec["bg"])
    if spec["mode"] == "vgrad":
        top, bottom = ImageColor_pair(spec["bg"], spec["bg2"])
        for i in range(H * S):
            t = i / (H * S - 1)
            im.paste(tuple(int(top[k] + (bottom[k] - top[k]) * t) for k in range(3)) + (255,),
                     (0, i, W * S, i + 1))
    return im


def ImageColor_pair(a, b):
    def rgb(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))
    return rgb(a), rgb(b)


def render_bg(spec, lay):
    im = backdrop(spec)
    d = ImageDraw.Draw(im, "RGBA")

    if spec["mode"] == "grid":
        line = (11, 58, 91, 40)
        for gx in range(0, W * S, 12 * S):
            d.line([(gx, 0), (gx, H * S)], fill=line, width=1)
        for gy in range(0, H * S, 12 * S):
            d.line([(0, gy), (W * S, gy)], fill=line, width=1)
    if spec["mode"] == "scan":
        for gy in range(0, H * S, 4 * S):
            d.line([(0, gy), (W * S, gy)], fill=(255, 176, 0, 16), width=S)

    head = fnt("consola.ttf", 10)
    small = fnt("consola.ttf", 9)
    label = fnt("consola.ttf", 8)

    if spec["header"]:
        d.text((12 * S, 12 * S), spec["header"], font=head, fill=spec["dim"], anchor="lt")

    cx, cy = lay["colon_pos"]
    dot_w = max(5, round(lay["cw"] * 0.22))
    for t in (0.34, 0.64):
        dy = cy + lay["ch"] * t
        d.rounded_rectangle([cx * S, dy * S, (cx + dot_w) * S, (dy + dot_w) * S],
                            radius=dot_w * S // 3, fill=spec["time"])

    for y in (lay["rule1"], lay["steps_y"] + lay["mh"] + 12):
        d.line([(12 * S, y * S), (182 * S, y * S)], fill=spec["dim"], width=1)

    if spec["deco"] == "dots":
        for gx in range(16, 182, 8):
            d.ellipse([gx * S, 326 * S, (gx + 3) * S, 329 * S], fill=spec["dim"])

    d.text((12 * S, lay["steps_label"] * S), "S T E P S", font=label, fill=spec["dim"], anchor="lt")
    d.text((182 * S, (lay["steps_y"] + 4) * S), "/ 10k", font=label, fill=spec["dim"], anchor="rt")
    d.text((12 * S, lay["hr_label"] * S), "H E A R T", font=label, fill=spec["dim"], anchor="lt")

    hx, hy = 14, lay["hr_y"] + 8
    heart(d, hx, hy, 11, spec.get("love_color", spec["accent"]))

    for i in range(24):
        gx = 12 + i * 7
        d.rounded_rectangle([gx * S, 298 * S, (gx + 5) * S, 303 * S],
                            radius=S, fill=spec["accent"] if i % 5 == 0 else spec["dim"])

    foot = spec["footer"]
    tw = d.textlength(foot, font=small) / S
    hw = 9 if spec.get("love") else 0
    total = tw + (6 + hw if hw else 0)
    fx = (W - total) / 2
    d.text((fx * S, 335 * S), foot, font=small, fill=spec["dim"], anchor="lt")
    if hw:
        heart(d, fx + tw + 6 + hw / 2, 340, hw, spec.get("love_color", spec["accent"]))
    return im.resize((W, H), Image.LANCZOS)


def heart(d, cx, cy, size, fill):
    pts = []
    for i in range(160):
        a = 2 * math.pi * i / 160
        px = 16 * math.sin(a) ** 3
        py = -(13 * math.cos(a) - 5 * math.cos(2 * a) - 2 * math.cos(3 * a) - math.cos(4 * a))
        pts.append((cx * S + px * size * S / 32, cy * S + py * size * S / 32))
    d.polygon(pts, fill=fill)


def glyph(size, text, font, fill):
    im = Image.new("RGBA", (size[0] * S, size[1] * S), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.text((size[0] * S // 2, size[1] * S // 2), text, font=font, fill=fill, anchor="mm")
    return im.resize(size, Image.LANCZOS)


def build_resources(spec, lay):
    big_f = fnt(spec["font"], spec["size"])
    med_f = fnt(spec["font"], lay["med"])
    lab_f = fnt("consola.ttf", 12)
    big_cell = (lay["cw"], lay["ch"])
    med_cell = (lay["mw"], lay["mh"])

    res = {2: render_bg(spec, lay)}
    for n in range(10):
        res[3 + n] = glyph(big_cell, str(n), big_f, spec["time"])
        res[13 + n] = glyph(med_cell, str(n), med_f, spec["ink"])
    for n, name in enumerate(["MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"]):
        res[23 + n] = glyph((34, 15), name, lab_f, spec["accent"])
    for n, name in enumerate(["JAN", "FEB", "MAR", "APR", "MAY", "JUN",
                              "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]):
        res[30 + n] = glyph((32, 15), name, lab_f, spec["dim"])
    for n in range(42, 53):
        res[n] = Image.new("RGBA", (1, 1), (0, 0, 0, 0))
    res[53] = Image.new("RGBA", (10, lay["mh"]), (0, 0, 0, 0))
    res[54] = glyph((10, lay["mh"]), "-", med_f, spec["ink"])
    return res


def encode_proto(spec, lay):
    big = [f"{n:03}" for n in range(3, 13)]
    dx = 12
    proto = fb(1, element(0, [layer_single(0, "002", 0, 0)]))
    proto += fb(1, element(1, [
        layer_selected(0, 59, big[:3], *lay["h10"]),
        layer_selected(1, 60, big, *lay["h1"]),
        layer_selected(2, 61, big[:6], *lay["m10"]),
        layer_selected(3, 62, big, *lay["m1"]),
    ]))
    dp = lay["date_pos"]
    proto += fb(1, element(2, [
        layer_selected(0, 52, [f"{n:03}" for n in range(23, 30)], *dp["weekday"]),
        layer_combined(1, 17, *dp["day"]),
        layer_selected(2, 51, [f"{n:03}" for n in range(30, 42)], *dp["month"]),
    ]))
    proto += fb(1, element(3, containers=[
        container(0, 10, [layer_combined(0, 0, 12, lay["steps_y"])]),
        container(1, 11, [layer_combined(0, 2, 30, lay["hr_y"])]),
    ]))
    proto += fb(2, spec["title"]) + fb(3, spec["title"]) + fb(4, f"{W}x{H}")
    return proto


def preview(res, lay):
    im = res[2].copy()
    put = lambda n, xy: im.alpha_composite(res[n], xy)
    put(3, lay["h10"]); put(12, lay["h1"])
    put(3, lay["m10"]); put(4, lay["m1"])
    dp = lay["date_pos"]
    put(26, dp["weekday"])
    put(16, dp["day"]); put(17, (dp["day"][0] + lay["mw"], dp["day"][1]))
    put(39, dp["month"])
    for i, ch in enumerate("8432"):
        put(13 + int(ch), (12 + i * lay["mw"], lay["steps_y"]))
    put(20, (30, lay["hr_y"])); put(15, (30 + lay["mw"], lay["hr_y"]))
    return im


def build(spec):
    lay = layout(spec)
    if lay["hr_y"] + lay["mh"] > 330:
        raise ValueError(f"{spec['slug']}: layout overflows ({lay['hr_y'] + lay['mh']})")
    res = build_resources(spec, lay)
    proto = encode_proto(spec, lay)
    fat, resources = pack_resources(res)
    blob = assemble(proto, fat, resources)
    selftest(blob, res, proto)
    payload = payload_zip(blob, res, f"band10-{spec['slug']}")

    cover = preview(res, lay)
    cover.save(OUT / f"{spec['slug']}.png")
    out = OUT / f"band10-{spec['slug']}.hwt"
    import zipfile
    with zipfile.ZipFile(out, "w") as zf:
        for name, data in (
            ("com.huawei.watchface", payload),
            ("description.xml", description(spec).encode()),
            ("preview/cover.jpg", jpg(cover)),
            ("preview/icon_small.jpg", jpg(cover.resize((97, 184), Image.LANCZOS))),
        ):
            info = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            zf.writestr(info, data, compress_type=zipfile.ZIP_DEFLATED, compresslevel=9)
    return out, cover


def jpg(im):
    import io
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=92)
    return buf.getvalue()


def description(spec):
    name = f"band10-{spec['slug']}"
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<HwTheme>
  <title>{spec['title']}</title>
  <title-cn>{spec['title']}</title-cn>
  <author>fahru</author>
  <designer>fahru</designer>
  <screen>HWHD07</screen>
  <version>1.0.0</version>
  <font>Default</font>
  <font-cn>Default</font-cn>
</HwTheme>
"""


def sheet(covers):
    cols, pad, label_h = 5, 12, 18
    cw, chh = W, H
    sw = cols * cw + (cols + 1) * pad
    rows = math.ceil(len(covers) / cols)
    sh = rows * (chh + label_h) + (rows + 1) * pad
    im = Image.new("RGB", (sw, sh), "#11151A")
    d = ImageDraw.Draw(im)
    f = ImageFont.truetype(str(FONTS / "consola.ttf"), 12)
    for i, (name, cover) in enumerate(covers):
        x = pad + (i % cols) * (cw + pad)
        y = pad + (i // cols) * (chh + label_h + pad)
        im.paste(cover.convert("RGB"), (x, y))
        d.rectangle([x, y, x + cw - 1, y + chh - 1], outline="#2A323C")
        d.text((x, y + chh + 3), name, font=f, fill="#9AA5B1")
    return im


def main(png_only=False, only=None):
    OUT.mkdir(parents=True, exist_ok=True)
    specs = [s for s in VARIANTS if not only or s["slug"] == only]
    if png_only:
        for spec in specs:
            lay = layout(spec)
            preview(build_resources(spec, lay), lay).save(OUT / f"{spec['slug']}.png")
            print(f"{spec['slug']:10} png {lay['cw']}x{lay['ch']} hr_y={lay['hr_y']}")
        return
    covers = []
    for spec in specs:
        out, cover = build(spec)
        covers.append((spec["slug"], cover))
        print(f"{spec['slug']:10} {out.stat().st_size:>7} B  {out.name}")
    if only:
        return
    sh = sheet(covers)
    sh.save(OUT / "contact-sheet.png")
    sh.resize((sh.width * 2 // 3, sh.height * 2 // 3), Image.LANCZOS).save(OUT / "contact-sheet.jpg", quality=88)
    write_page()
    print(f"sheet: {OUT / 'contact-sheet.png'} ({sh.width}x{sh.height})")


def write_page():
    import base64
    b64 = base64.b64encode((OUT / "contact-sheet.jpg").read_bytes()).decode()
    legend = "".join(f"<li><b>{s['slug']}</b> — {s['title']}</li>" for s in VARIANTS)
    page = f"""<!doctype html>
<meta charset="utf-8"><title>Band 10 — 10 varian watchface</title>
<style>
body{{margin:0;padding:24px;background:#0d1117;color:#e6edf3;font:14px/1.6 ui-monospace,Consolas,monospace}}
h1{{font-size:16px;font-weight:600;margin:0 0 4px}}
p{{margin:0 0 18px;color:#8b949e}}
ul{{margin:0 0 20px;padding-left:18px;columns:2;color:#c9d1d9}}
img{{width:100%;max-width:1042px;border:1px solid #30363d;border-radius:8px;display:block}}
</style>
<h1>10 varian watchface — Huawei Band 10 (194×368)</h1>
<p>Semua memuat jam, tanggal, langkah, dan detak jantung. Skala 1:1 per sel.</p>
<ul>{legend}</ul>
<img src="data:image/jpeg;base64,{b64}">
"""
    (OUT / "index.html").write_text(page, encoding="utf-8")


if __name__ == "__main__":
    argv = sys.argv[1:]
    main("--png" in argv, argv[argv.index("--only") + 1] if "--only" in argv else None)
