"""Turn the kedy line-art PNG into ASCII art (art/kedy.txt).

Usage: python tools/kedy_to_ascii.py <image.png> [cols=58] [aspect=2.2] [fill=0.14] > art/kedy.txt

Lines become dense characters and the cat's facets get a light fill,
so the silhouette stays readable at small sizes.
Requires: pillow, numpy, scipy.
"""
import sys

import numpy as np
from PIL import Image
from scipy import ndimage

RAMP = " .':;!|lj%kmH@"


def main():
    path = sys.argv[1]
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 58
    aspect = float(sys.argv[3]) if len(sys.argv) > 3 else 2.2
    fill = float(sys.argv[4]) if len(sys.argv) > 4 else 0.14

    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    line = np.asarray(bg.convert("L")) < 128
    ys, xs = np.where(line)
    line = line[ys.min() - 4 : ys.max() + 5, xs.min() - 4 : xs.max() + 5]
    inside = ndimage.binary_fill_holes(ndimage.binary_closing(line, iterations=3))
    val = np.where(line, 1.0, np.where(inside, fill, 0.0))

    h, w = val.shape
    cw = w / cols
    ch = cw * aspect
    rows = int(np.ceil(h / ch))
    out = []
    for r in range(rows):
        s = ""
        for c in range(cols):
            cell = val[int(r * ch) : int(min(h, (r + 1) * ch)), int(c * cw) : int(min(w, (c + 1) * cw))]
            v = cell.mean() if cell.size else 0.0
            v = min(1.0, v ** 0.8 * 1.25)
            s += RAMP[int(round(v * (len(RAMP) - 1)))]
        if s.strip():
            out.append(s.rstrip())
    print("\n".join(out))


if __name__ == "__main__":
    main()
