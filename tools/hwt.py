"""Pack and check .hwt watchface packages for the Huawei Band 10."""

import argparse
import io
import struct
import zipfile
from pathlib import Path
from xml.etree import ElementTree

SCREEN = "368*194"
THEMES = {"HWHD07": SCREEN, "HNHD02": SCREEN}
DESCRIPTION = """<?xml version="1.0" encoding="UTF-8"?>
<HwTheme>
  <title>{title}</title>
  <author>{author}</author>
  <designer>{designer}</designer>
  <screen>{theme}</screen>
  <version>{version}</version>
</HwTheme>
"""


def payload_kind(data: bytes) -> str:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as nested:
            if "watchface.bin" in nested.namelist():
                return "zip/watchface.bin"
            return "zip"
    except zipfile.BadZipFile:
        pass
    if len(data) > 16:
        ver, _, proto, fat, _, res, _ = struct.unpack("<BBHHHII", data[:16])
        if ver == 2 and 16 + proto + fat + res == len(data):
            return f"band/proto+fat+res ({fat // 8} slots)"
    return "raw"


def check(path: Path) -> tuple[list[str], str]:
    errors = []
    kind = "none"
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "description.xml" not in names:
            return ["missing description.xml"], kind
        root = ElementTree.fromstring(zf.read("description.xml").lstrip(b"\xef\xbb\xbf"))
        if root.tag not in {"HwTheme", "HnTheme"}:
            errors.append(f"unexpected root element {root.tag!r}")
        theme = (root.findtext("screen") or "").strip()
        if THEMES.get(theme) != SCREEN:
            errors.append(f"theme {theme!r} does not target Band 10 ({SCREEN})")
        if "preview/cover.jpg" not in names:
            errors.append("missing preview/cover.jpg")
        payload = "com.honor.watchface" if root.tag == "HnTheme" else "com.huawei.watchface"
        if payload not in names:
            errors.append(f"missing {payload}")
        else:
            kind = payload_kind(zf.read(payload))
    return errors, kind


def pack(src: Path, dst: Path, theme="HWHD07", title="band10-terminal", author="fahru", version="1.0"):
    meta = DESCRIPTION.format(
        title=title, author=author, designer=author, theme=theme, version=version
    )
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("description.xml", meta)
        for name in ("preview/cover.jpg", "com.huawei.watchface"):
            zf.write(src / name, name)
    return dst


def selftest():
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp)
        (src / "preview").mkdir()
        (src / "preview" / "cover.jpg").write_bytes(b"\xff\xd8\xff\xd9")
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as inner:
            inner.writestr("watchface.bin", b"\x00" * 16)
        (src / "com.huawei.watchface").write_bytes(buf.getvalue())

        good = pack(src, src / "good.hwt")
        errors, kind = check(good)
        assert errors == [], errors
        assert kind == "zip/watchface.bin", kind

        bad = pack(src, src / "bad.hwt", theme="HWHD01")
        errors, _ = check(bad)
        assert any("Band 10" in e for e in errors), errors

        (src / "com.huawei.watchface").write_bytes(b"not-a-zip")
        errors, kind = check(pack(src, src / "raw.hwt"))
        assert errors == [] and kind == "raw", (errors, kind)

    print("selftest ok")


def main(argv):
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("pack")
    p.add_argument("src", type=Path)
    p.add_argument("dst", type=Path)
    p.add_argument("--theme", default="HWHD07")
    p.add_argument("--title", default="band10-terminal")

    c = sub.add_parser("check")
    c.add_argument("path", type=Path)

    sub.add_parser("selftest")

    a = ap.parse_args(argv)
    if a.cmd == "selftest":
        selftest()
        return 0
    if a.cmd == "pack":
        print(pack(a.src, a.dst, theme=a.theme, title=a.title))
        return 0
    errors, kind = check(a.path)
    print("\n".join(errors) if errors else "ok")
    print(f"payload: {kind}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main(__import__("sys").argv[1:]))
