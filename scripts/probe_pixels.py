"""Measure a bridge screenshot: the evidence for what a theme colour paints (probes 46-48).

Usage:
    python scripts/probe_pixels.py sample <png> X,Y [X,Y ...]
    python scripts/probe_pixels.py count  <png> NAME=RRGGBB [NAME=RRGGBB ...]

Standard library only (no Pillow). Reads 8-bit RGB/RGBA, non-interlaced PNGs, which is what the
Desktop bridge writes. Coordinates are in the ORIGINAL image (a capture shown at 2000 px wide is
2834 px: multiply displayed coordinates by 1.417). `sample` prints a pixel's colour, so read solid
fills and never anti-aliased text. `count` reports, per colour, exact pixels, pixels within 6 per
channel (thin lines are anti-aliased) and the bounding box of the near matches in displayed
(2000 px wide) coordinates, so a loud candidate colour can be traced to the element that draws it.
"""

import struct
import sys
import zlib

SHOWN_WIDTH = 2000


def read_png(path: str) -> tuple[int, int, int, list[bytearray]]:
    with open(path, "rb") as fh:
        data = fh.read()
    if data[:8] != b"\x89PNG\r\n\x1a\n":
        sys.exit(f"{path}: not a PNG")
    pos, idat, ihdr = 8, b"", None
    while pos < len(data):
        size, kind = struct.unpack(">I4s", data[pos:pos + 8])
        body = data[pos + 8:pos + 8 + size]
        if kind == b"IHDR":
            ihdr = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + size
    width, height, depth, ctype, _, _, interlace = ihdr
    if depth != 8 or interlace or ctype not in (2, 6):
        sys.exit(f"{path}: only 8-bit RGB or RGBA, not interlaced, is supported")
    bpp = 3 if ctype == 2 else 4
    raw, stride = zlib.decompress(idat), width * bpp
    rows, prev = [], bytearray(stride)
    for y in range(height):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        for i in range(stride):
            a = line[i - bpp] if i >= bpp else 0
            b = prev[i]
            c = prev[i - bpp] if i >= bpp else 0
            if kind == 1:
                line[i] = (line[i] + a) & 255
            elif kind == 2:
                line[i] = (line[i] + b) & 255
            elif kind == 3:
                line[i] = (line[i] + (a + b) // 2) & 255
            elif kind == 4:
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(line)
        prev = line
    return width, height, bpp, rows


def main(argv: list[str]) -> int:
    if len(argv) < 4 or argv[1] not in ("sample", "count"):
        sys.exit(__doc__)
    width, _, bpp, rows = read_png(argv[2])
    if argv[1] == "sample":
        for xy in argv[3:]:
            x, y = map(int, xy.split(","))
            r, g, b = rows[y][x * bpp:x * bpp + 3]
            print(xy, f"#{r:02X}{g:02X}{b:02X}")
        return 0
    scale = SHOWN_WIDTH / width
    for item in argv[3:]:
        name, hexval = item.split("=")
        want = bytes.fromhex(hexval.lstrip("#"))
        exact = near = 0
        xs, ys = [], []
        for y, row in enumerate(rows):
            for x in range(width):
                px = row[x * bpp:x * bpp + 3]
                exact += px == want
                if max(abs(px[0] - want[0]), abs(px[1] - want[1]), abs(px[2] - want[2])) <= 6:
                    near += 1
                    xs.append(x)
                    ys.append(y)
        box = (f"displayed x {int(min(xs) * scale)}-{int(max(xs) * scale)}, "
               f"y {int(min(ys) * scale)}-{int(max(ys) * scale)}") if xs else ""
        print(f"{name:28} #{hexval.lstrip('#').upper()}  exact {exact:6}  within6 {near:6}  {box}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
