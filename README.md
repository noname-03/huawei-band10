# Huawei Band 10 watchface builder

Tooling to build custom watchfaces for the **Huawei Band 10** without Theme Studio.
Everything here was derived by unpacking real `.hwt` files; no vendor SDK is used.

Target: `HWHD07`, 194×368 px, verified on Band 10 firmware HarmonyOS 5.0.0.167.
Files built for the Band 8 (`HWHD07`) also install on Band 10 — confirmed with a control face.

## Files

| Path | Purpose |
|---|---|
| `tools/build_terminal.py` | Original single-face builder. Owns the `.hwt`/`watchface.bin` encoder, protobuf writer, RLE codec, self-test. |
| `tools/build_variants.py` | Variant generator. Imports the encoder from `build_terminal.py`, renders designs, emits `.hwt` + previews. |
| `tools/hwt.py` | Validator. `check <file>` / `selftest`. |
| `dist/band10-terminal.hwt` | First working face. |
| `dist/variants/` | 11 variants, preview PNGs, contact sheet. `band10-carbon-new.hwt` is the one in daily use. |
| `tools/gadgetbridge-0.95.1.apk` | Installer app, F-Droid developer-signed build. See [Gadgetbridge](#gadgetbridge) for source and newer versions. |

Commands:

```
python tools/build_variants.py            # all variants
python tools/build_variants.py --png      # previews only, no .hwt
python tools/build_variants.py --only carbon-new
python tools/hwt.py check dist/variants/band10-carbon-new.hwt
```

## Container format

`.hwt` is a plain zip:

```
com.huawei.watchface     raw watchface.bin, or a zip that contains watchface.bin
description.xml          <HwTheme>, <screen> HWHD07
preview/cover.jpg
preview/icon_small.jpg
```

`description.xml` is parsed by Gadgetbridge for metadata only; the band reads the binary.

### watchface.bin

```
offset 0   16 bytes  struct.pack("<BBHHHII",
                     2, 0, len(proto), len(fat), 0, len(resources), 0)
offset 16  proto      TemplateWatch2 protobuf
after      fat        (u32 offset, u32 length) per resource
after      resources  b"UUUU\x01\x00\x00\x01" + image blobs
```

FAT offsets are relative to the start of the resources blob (first entry is 8).
Slot 0 is an unused 1×1 placeholder. A layer's `resName` of `"042"` means
`A100_042.png`, which lives in **FAT slot 41** — i.e. `int(name) - 1`.

### Resource image encoding

```
0x45 0x23 0x88 0x88   magic
u16 width, u16 height (little endian)
pixels                BGRA, RLE-compressed
```

RLE: an escape sequence `0x89 0x67 0x45 0x23` followed by `BGRA` and a `u32 count`
repeats that colour `count` times. Runs of 1–3 pixels (and any pixel equal to the
escape word) are written raw. This is byte-for-byte the same scheme Theme Studio emits.

## Protobuf: TemplateWatch2

Field numbers were recovered from a working Band 8 face and are confirmed against
protobufjs output. **Delimited fields must be wrapped**: `elements` is a repeated
field 1, so every element is `0x0A <len> <element bytes>`. Writing element fields at
the top level produces a face that installs cleanly and renders nothing (this bug
cost a full debugging cycle — keep the `proto[0] == 0x0A` assertion in `selftest`).

```
TemplateWatch2
  f1  repeated Element
  f2  titleEn (string)
  f3  titleCn (string)
  f4  screenSize (string, "194x368")

Element
  f1  label (int)        0 background, 1 time, 2 date, 3 widgets
  f2  isSupportOption (bool)
  f5  repeated Layer
  f8  repeated Container

Layer
  f1  index
  f2  drawType           1 = singleRes, 2 = selectedRes, 3 = combinedRes
  f4  singleRes   { f1 resName, f2 position }
  f5  selectedRes { f1 repeated resName, f2 position, f3 valueType }
  f6  combinedRes { f1 repeated resName, f2 repeated resDefault,
                    f3 position, f4 alignType, f5 valueType, f6 resSign }

Container
  f1  index
  f2  isSupportOption
  f5  rect { f1 x, f2 y, f3 width, f4 height }
  f6  repeated Layer
  f8  dataType

position / rect components are plain varints.
```

`selectedRes` maps value → image by list index (index 0 renders when the value is 0).
`combinedRes` renders a multi-digit number; `resDefault` supplies the images used for
leading zero positions (convention: `["013", "053"]`).

### valueType / dataType

Observed values, reused as-is:

| valueType | Meaning |
|---|---|
| 0 | steps |
| 1 | calories |
| 2 | heart rate |
| 4 | battery (pair with `resSign`) |
| 9 | steps (second flavour, seen in a container) |
| 17 | day of month |
| 51 | month |
| 52 | weekday |
| 53 | weather icon |
| 59 / 60 | hour tens / ones |
| 61 / 62 | minute tens / ones |
| 63 / 64 | second tens / ones |

`dataType` seen on containers: 10 (steps), 11 (heart rate), 12 (calories),
17 (steps), 21 (weather + battery).

**Unknown, do not guess:**

- `valueType` for sleep duration. Huawei documents Sleep as a supported data type but
  never publishes the numeric mapping. Needs a probe face that renders many candidates
  at once, or a genuine Band face that already shows sleep.
- Whether `Container.rect` acts as a tap target. Tapping the steps/heart regions on an
  installed face has not been tested yet. If it does, per-region actions are possible;
  no evidence either way.

## Installing on the band

Gadgetbridge is the only public installer. Huawei Health cannot import a watchface.

Order matters. **Huawei Health must pair with the band first.**

1. Pair normally in Huawei Health. Let it sync.
2. Turn Health off: `adb shell pm disable-user --user 0 com.huawei.health`
3. Install Gadgetbridge, open it, grant Bluetooth / Nearby devices permissions.
4. Add device → long-press the band → **Auth key** (or Device specific settings →
   **Huawei Account**) → enter the 17-digit Huawei *userId*.
5. Connect, then open the `.hwt` from storage → Gadgetbridge → Install.
6. `adb shell pm enable com.huawei.health` and reopen Health.

The 17-digit userId comes from `cloud.huawei.com` cookies (`userId`), or
`grep old_user_id /data/data/com.huawei.health/shared_prefs/login_data.xml` on a rooted
phone, or `adb logcat | grep huid=`. It is **not** the Huawei ID used for login.

### Why the order is fixed

Gadgetbridge derives the auth key from the userId, but it creates its own pairing
record on the band. Huawei Health cannot adopt that record — it reports the band as
bound elsewhere (`DEVMGR_DevicePairGuideActivity ... state : 9`) and only offers a
reset guide. Going Health → Gadgetbridge works. The reverse does not.

Consequences:

- Do not factory reset the band to "fix" Gadgetbridge problems if a watchface matters;
  a reset wipes installed faces.
- Each Gadgetbridge upload creates a **new** watchface entry with a random name
  (`<9 digits>_1.0.0`). Old entries stay in the band list. When a freshly installed
  face appears unchanged, the old entry is usually the one being displayed.
- A firmware update removes custom faces. Keep the `.hwt` files.

Gadgetbridge upload path detail (`HuaweiFwHelper.parseAsWatchFace`): if
`com.huawei.watchface` is a zip, it extracts `watchface.bin` from it; otherwise it
uploads the file as-is. Both forms therefore send identical bytes — wrapping in a zip
changes nothing on the wire.

## Design notes

- Layout lives in `VARIANTS` in `tools/build_variants.py`; `layout()` derives all
  positions from `size`, `font` and a few offsets.
- Clock cell width is measured from the actual font advance
  (`ImageFont.getlength("0")`), not a fixed ratio. Proportional fonts (bahnschrift)
  need this or the digits look spaced out.
- Text is rendered at 3× and downsampled; resource cells must be at least as tall as
  the glyph or PIL clips it.
- Resource numbering is fixed: `002` background, `003–012` large digits,
  `013–022` medium digits, `023–029` weekdays, `030–041` months, `042–052` filler,
  `053` blank, `054` sign.

## Gadgetbridge

`tools/gadgetbridge-0.95.1.apk` is the F-Droid developer-signed build, redistributed
here unmodified. Its original filename is
`nodomain.freeyourgadget.gadgetbridge_255_01cce93.apk` (versionCode 255).

Gadgetbridge is developed by the Freeyourgadget project and contributors.
Copyright belongs to them; it is licensed under **AGPL-3.0**, so any modified
version must be published under the same terms.

- Source (canonical): <https://codeberg.org/Freeyourgadget/Gadgetbridge>
- Releases and nightly builds: <https://codeberg.org/Freeyourgadget/Gadgetbridge/releases>
- F-Droid page (download link, upstream for updates):
  <https://f-droid.org/packages/nodomain.freeyourgadget.gadgetbridge/>
- Documentation: <https://gadgetbridge.org/>

Check F-Droid or Codeberg for newer builds. The F-Droid-signed APK and the
developer-signed APK carry different signatures and cannot be installed over each
other — switching requires uninstalling first, which also deletes Gadgetbridge's
local data.

Do not use the Play Store listing or APK mirror sites; they are not upstream.

## References

The binary format was reconstructed from these public sources:

- <https://github.com/menezesx2k26-byte/lab-band8-kanagawa-watchface> — working
  `HWHD07` face and its builder. Source of the header layout, FAT, RLE image codec
  and the `TemplateWatch2` field numbers used here.
- <https://github.com/Kuberwastaken/Huawhoop> — Band 10 protocol work, watchface
  inventory and the `HWHD07` → `368*194` mapping.
- <https://github.com/leeorichi/huawei-watch-face-maker> — early extractor that
  documented the image container layout.
- <https://gadgetbridge.org/basics/pairing/huawei-honor-pairing/> — the account-ID
  pairing procedure, including the rule that the band must not be unpaired from the
  vendor app.
