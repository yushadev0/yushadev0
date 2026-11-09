"""Turn the kedy line-art PNG into /\\|_- line ASCII art (art/kedy.txt).

Usage: python tools/kedy_to_ascii.py <image.png> [cols=70] [aspect=2.1] > art/kedy.txt

1. Every facet (white region inside the cat) and the outer silhouette is grown
   to the centre of the black lines and simplified to a polygon.
2. Polygon corners that sit on the same junction are merged, so lines shared by
   two facets are drawn once.
3. Each edge is drawn on a character grid by its slope: | for steep lines,
   / and \\ for diagonals, _ and - for flat ones (picked by height in the cell).

Requires: pillow, numpy, scipy, scikit-image.
"""
import math
import sys

import numpy as np
from PIL import Image
from scipy import ndimage
from skimage import measure

BS = "\\"


def load_lines(path):
    im = Image.open(path).convert("RGBA")
    bg = Image.new("RGBA", im.size, (255, 255, 255, 255))
    bg.alpha_composite(im)
    a = np.asarray(bg.convert("L")) < 128
    ys, xs = np.where(a)
    return a[ys.min() - 20 : ys.max() + 21, xs.min() - 20 : xs.max() + 21]


def facet_polygons(a):
    dt = ndimage.distance_transform_edt(a)
    half = float(np.median(dt[(dt > 0) & (dt == ndimage.maximum_filter(dt, 5))]))
    lab, n = ndimage.label(~a)
    bg_label = lab[0, 0]
    polys = []
    for i in range(1, n + 1):
        m = lab == i
        if i == bg_label:
            m = ndimage.binary_fill_holes(~(ndimage.distance_transform_edt(~m) <= half + 1.5))
        elif m.sum() < 40:
            continue
        else:
            m = ndimage.distance_transform_edt(~m) <= half + 1.5
        contour = max(measure.find_contours(m.astype(float), 0.5), key=len)
        poly = measure.approximate_polygon(contour, tolerance=5)
        polys.append([(float(x), float(y)) for y, x in poly])
    return polys


def snap_edges(polys, rad=20.0):
    pts, idx = [], []
    for p in polys:
        p = p[:-1] if p[0] == p[-1] else p
        idx.append(list(range(len(pts), len(pts) + len(p))))
        pts.extend(p)
    P = np.array(pts)
    parent = list(range(len(P)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    D = np.hypot(P[:, None, 0] - P[None, :, 0], P[:, None, 1] - P[None, :, 1])
    for i in range(len(P)):
        for j in np.where(D[i] < rad)[0]:
            parent[find(i)] = find(j)
    groups = {}
    for i in range(len(P)):
        groups.setdefault(find(i), []).append(i)
    V = {r: P[m].mean(0) for r, m in groups.items()}

    edges = set()
    for ii in idx:
        for a, b in zip(ii, ii[1:] + ii[:1]):
            ra, rb = find(a), find(b)
            if ra != rb:
                edges.add(tuple(sorted((ra, rb))))

    def dist(p, a, b):
        ab = b - a
        t = np.clip(np.dot(p - a, ab) / np.dot(ab, ab), 0, 1)
        return float(np.hypot(*(a + t * ab - p)))

    out = set()
    for a, b in edges:  # split edges that pass through another junction
        A, B = V[a], V[b]
        on = [
            r for r in V
            if r not in (a, b) and dist(V[r], A, B) < rad * 0.5
            and 0.05 < np.dot(V[r] - A, B - A) / np.dot(B - A, B - A) < 0.95
        ]
        chain = [a] + sorted(on, key=lambda r: np.dot(V[r] - A, B - A)) + [b]
        out.update(tuple(sorted(e)) for e in zip(chain, chain[1:]))
    return [(*V[a], *V[b]) for a, b in sorted(out)]


def draw(edges, shape, cols, aspect, min_len=0.5):
    H, W = shape
    cw = W / cols
    ch = cw * aspect
    rows = int(math.ceil(H / ch)) + 1
    g = [[" "] * cols for _ in range(rows)]

    def put(r, c, s):
        if 0 <= r < rows and 0 <= c < cols and g[r][c] == " ":
            g[r][c] = s

    segs = sorted(
        ((math.hypot(x1 - x0, y1 - y0), x0, y0, x1, y1) for x0, y0, x1, y1 in edges),
        reverse=True,
    )
    for length, x0, y0, x1, y1 in segs:
        if length < min_len * cw:
            continue
        dx, dy = x1 - x0, y1 - y0
        th = math.degrees(math.atan2(abs(dy), abs(dx)))
        diag = "/" if dx * dy < 0 else BS
        if abs(dx) / cw >= abs(dy) / ch:  # walk columns
            if x0 > x1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            for c in range(int(x0 // cw), int(x1 // cw) + 1):
                xa, xb = max(x0, c * cw), min(x1, (c + 1) * cw)
                if xb - xa < cw * 0.35:
                    continue
                ya = y0 + (xa - x0) * dy / dx
                yb = y0 + (xb - x0) * dy / dx
                y = (ya + yb) / 2
                r = int(y // ch)
                f = y / ch - r
                if th >= 30 or (int(ya / ch) != int(yb / ch) and th > 12):
                    put(r, c, diag)
                elif f < 0.35:
                    put(r - 1, c, "_")
                elif f < 0.62:
                    put(r, c, "-")
                else:
                    put(r, c, "_")
        else:  # walk rows
            if y0 > y1:
                x0, y0, x1, y1 = x1, y1, x0, y0
            for r in range(int(y0 // ch), int(y1 // ch) + 1):
                ya, yb = max(y0, r * ch), min(y1, (r + 1) * ch)
                if yb - ya < ch * 0.35:
                    continue
                x = x0 + ((ya + yb) / 2 - y0) * dx / dy
                put(r, int(x // cw), "|" if th > 76 else diag)

    lines = ["".join(row).rstrip() for row in g]
    while lines and not lines[-1]:
        lines.pop()
    while lines and not lines[0]:
        lines.pop(0)
    return lines


def main():
    path = sys.argv[1]
    cols = int(sys.argv[2]) if len(sys.argv) > 2 else 70
    aspect = float(sys.argv[3]) if len(sys.argv) > 3 else 2.1
    a = load_lines(path)
    edges = snap_edges(facet_polygons(a))
    print("\n".join(draw(edges, a.shape, cols, aspect)))


if __name__ == "__main__":
    main()
