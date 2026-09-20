"""Rebuild the animated Sham mascot SVGs and the extension icons from public/sham-mascot.png.

The source PNG is upscaled AI pixel art with no clean grid, so it is
re-pixelated: median colour per 12px block, snapped to a small palette, then
emitted as one <path> of merged rects per colour. The tail, magnifier and eye
are split into their own groups so CSS can animate them independently.

Run from frontend/:  python scripts/mascot_to_svg.py
Needs: pip install pillow numpy
Writes: public/sham-mascot.svg (idle), public/sham-mascot-scanning.svg, and
public/icon/{16,32,48,96,128}.png (a drawn deerstalker)
"""
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "public" / "sham-mascot.png"
BLOCK = 12
N_COLORS = 14
PAD = 4  # empty margin (cells) so animated parts never clip at the edge
MERGE_DIST = 24  # palette entries closer than this collapse into one


def pixelate():
    a = np.array(Image.open(SRC).convert("RGBA"))
    ys, xs = np.where(a[..., 3] > 128)
    crop = a[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
    h, w = (crop.shape[0] // BLOCK) * BLOCK, (crop.shape[1] // BLOCK) * BLOCK
    blocks = (
        crop[:h, :w]
        .reshape(h // BLOCK, BLOCK, w // BLOCK, BLOCK, 4)
        .transpose(0, 2, 1, 3, 4)
        .reshape(h // BLOCK, w // BLOCK, BLOCK * BLOCK, 4)
    )
    opaque = (blocks[..., 3] > 128).mean(axis=2) > 0.5
    rgb = np.median(blocks[..., :3], axis=2).astype(np.uint8)
    q = Image.fromarray(rgb).convert("RGB").quantize(
        colors=N_COLORS, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE
    )
    pal = np.array(q.getpalette()[: N_COLORS * 3]).reshape(-1, 3)
    idx = np.array(q)

    # Collapse near-duplicate palette entries (the outline quantizes to ~5 blacks).
    counts = np.bincount(idx[opaque], minlength=len(pal))
    kept, remap = [], {}
    for c in np.argsort(-counts):
        for k in kept:
            if np.linalg.norm(pal[c].astype(int) - pal[k].astype(int)) < MERGE_DIST:
                remap[c] = k
                break
        else:
            kept.append(c)
            remap[c] = c
    idx = np.vectorize(remap.get)(idx)
    return idx, pal, opaque


def hexcolor(rgb):
    return "#%02x%02x%02x" % tuple(int(v) for v in rgb)


def runs_path(idx, pal, mask, colors=None):
    """One <path> per colour; horizontal runs merged into single rects."""
    rows, cols = idx.shape
    per_color = {}
    for r in range(rows):
        c = 0
        while c < cols:
            if not mask[r, c]:
                c += 1
                continue
            k = idx[r, c]
            start = c
            while c < cols and mask[r, c] and idx[r, c] == k:
                c += 1
            per_color.setdefault(k, []).append(f"M{start} {r}h{c - start}v1h-{c - start}z")
    return "".join(
        f'<path fill="{hexcolor(pal[k])}" d="{"".join(d)}"/>' for k, d in sorted(per_color.items())
    )


def region(shape, rows, cols):
    m = np.zeros(shape, bool)
    m[rows[0] : rows[1] + 1, cols[0] : cols[1] + 1] = True
    return m


ICON_SIZES = (16, 32, 48, 96, 128)

# Hat palette, taken from the mascot so the icon matches it.
OUTLINE = (1, 6, 14)
MID = (27, 136, 173)
TEAL = (25, 115, 150)
NAVY = (14, 55, 81)
LIGHT = (166, 241, 244)


def _ellipse(u, v, cx, cy, rx, ry):
    return ((u - cx) / rx) ** 2 + ((v - cy) / ry) ** 2 <= 1


def draw_hat(n):
    """A complete deerstalker, side view facing right, on an n x n pixel grid.

    Geometry is defined in a 32x32 design space and sampled at pixel centres, so
    the same hat can be drawn at any grid size (the small sizes just get fewer,
    chunkier details). Outline is added last as a 1px ring around the shape.
    """
    s = 32 / n
    fill = {}
    for y in range(n):
        for x in range(n):
            u = (x + 0.5) * s
            v = (y + 0.5) * s - 2  # shift down so the hat sits centred vertically

            # Low dome with a peak sticking straight out each end, like the hat in profile.
            back_visor = 1 <= u <= 11 and 18.2 + (11 - u) * 0.08 <= v <= 21.6 + (11 - u) * 0.08
            front_visor = 21 <= u <= 31 and 18.2 + (u - 21) * 0.08 <= v <= 21.6 + (u - 21) * 0.08
            crown = _ellipse(u, v, 16, 18.5, 10.5, 8.5) and v <= 18.8
            band = abs(u - 16) <= 10.7 and 17.6 <= v <= 19.8
            loop = _ellipse(u, v, 12.8, 8.2, 3.5, 2.3) or _ellipse(u, v, 19.2, 8.2, 3.5, 2.3)
            knot = abs(u - 16) <= 1.6 and 6.4 <= v <= 10.5

            color = None
            if back_visor:
                color = NAVY if v > 20.6 + (11 - u) * 0.08 else TEAL
            if front_visor:
                color = NAVY if v > 20.6 + (u - 21) * 0.08 else MID
            if loop:
                color = MID
            if crown:
                vstripe, hstripe = (u % 5) < 1.6, (v % 5) < 1.6
                color = NAVY if vstripe and hstripe else TEAL if vstripe or hstripe else MID
                if _ellipse(u, v, 12.5, 14.4, 2.4, 1.4):
                    color = LIGHT  # shine
            if band:
                color = NAVY
            if knot:
                color = TEAL
            if color:
                fill[(x, y)] = color

    img = np.zeros((n, n, 4), np.uint8)
    for (x, y), color in fill.items():
        img[y, x] = [*color, 255]
    for y in range(n):
        for x in range(n):
            if (x, y) in fill:
                continue
            if any((x + dx, y + dy) in fill for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))):
                img[y, x] = [*OUTLINE, 255]
    return Image.fromarray(img)


def write_icons():
    """Extension icons: a full deerstalker hat, drawn (not cut from the mascot,
    whose hat is half hidden by the ear and forehead). Each size uses a whole
    multiple of a native pixel grid so the edges stay hard."""
    out = ROOT / "public" / "icon"
    native = {16: (16, 1), 32: (32, 1), 48: (24, 2), 96: (32, 3), 128: (32, 4)}  # size: (grid, scale)
    for size, (grid, scale) in native.items():
        draw_hat(grid).resize((size, size), Image.NEAREST).save(out / f"{size}.png")
    print(f"icons: {', '.join(map(str, ICON_SIZES))}px")


def main():
    idx, pal, opaque = pixelate()
    rows, cols = idx.shape
    R, C = np.indices(idx.shape)
    write_icons()

    # --- split into parts (grid coordinates, found by inspecting the pixelated sprite) ---
    tail = opaque & (R >= 22) & (R <= 52) & (C <= 19)
    tail_only = tail & (C < 17)  # cols 17-19 stay in the body too, so shifting the tail never leaves a gap
    magnifier = opaque & (R <= 42) & ((C >= 74) | ((C >= 73) & (R >= 29)) | ((C >= 71) & (R >= 40)))
    magnifier_only = magnifier & (R <= 38)  # handle rows 39-42 also stay in the body, same reason

    body = opaque & ~tail_only & ~magnifier_only

    # --- blink: patch fur over the eye, then draw a closed-eye line ---
    # The eye straddles the darker upper fur (rows 18-19) and the light muzzle (rows 20-21).
    outline = min(range(len(pal)), key=lambda k: int(pal[k].sum()) if (idx == k).any() else 10**6)
    eye_layer = (
        runs_path(np.full(idx.shape, idx[18, 54]), pal, region(idx.shape, (18, 19), (55, 58)))
        + runs_path(np.full(idx.shape, idx[21, 54]), pal, region(idx.shape, (20, 21), (55, 58)))
        + runs_path(np.full(idx.shape, outline), pal, region(idx.shape, (19, 19), (55, 58)))
    )

    parts = {
        "body": runs_path(idx, pal, body),
        "tail": runs_path(idx, pal, tail),
        "magnifier": runs_path(idx, pal, magnifier),
        "blink": eye_layer,
    }

    for name, css in (("sham-mascot.svg", IDLE_CSS), ("sham-mascot-scanning.svg", SCANNING_CSS)):
        svg = (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-{PAD} -{PAD} {cols + 2 * PAD} {rows + 2 * PAD}" '
            f'shape-rendering="crispEdges">'
            f"<style>{css}</style>"
            f'<g class="bob"><g class="sniff">'
            f'{parts["body"]}'
            f'<g class="tail">{parts["tail"]}</g>'
            f'<g class="mag">{parts["magnifier"]}</g>'
            f'<g class="blink">{parts["blink"]}</g>'
            f"</g></g></svg>"
        )
        (ROOT / "public" / name).write_text(svg)
        print(f"{name}: {len(svg) / 1024:.1f} KB, {cols}x{rows} cells")


# Units are grid cells (1 unit = 1 sprite pixel). steps(1) holds each keyframe then
# jumps, so movement reads as pixel-art frames rather than a smooth slide.
COMMON_CSS = """
.bob,.sniff,.tail,.mag,.blink{animation-timing-function:steps(1,end);animation-iteration-count:infinite}
.blink{opacity:0}
@media (prefers-reduced-motion:reduce){.bob,.sniff,.tail,.mag,.blink{animation:none}}
"""

IDLE_CSS = COMMON_CSS + """
.bob{animation-name:bob;animation-duration:1.2s}
.tail{animation-name:wag;animation-duration:.8s}
.mag{animation-name:hover;animation-duration:1.6s}
.blink{animation-name:blink;animation-duration:4s}
@keyframes bob{0%{transform:translateY(0)}50%{transform:translateY(-1px)}}
@keyframes wag{0%{transform:translateX(0)}25%{transform:translateX(-1px)}50%{transform:translateX(0)}75%{transform:translateX(1px)}}
@keyframes hover{0%{transform:translateY(0)}50%{transform:translateY(-1px)}}
@keyframes blink{0%,92%{opacity:0}92.01%,96%{opacity:1}96.01%,100%{opacity:0}}
"""

SCANNING_CSS = COMMON_CSS + """
.bob{animation-name:bob;animation-duration:.5s}
.sniff{animation-name:sniff;animation-duration:1.2s}
.tail{animation-name:wag;animation-duration:.4s}
.mag{animation-name:sweep;animation-duration:1.2s}
@keyframes bob{0%{transform:translateY(0)}50%{transform:translateY(-1px)}}
@keyframes sniff{0%{transform:translateX(0)}50%{transform:translateX(1px)}}
@keyframes wag{0%{transform:translateX(0)}25%{transform:translateX(-1px)}50%{transform:translateX(0)}75%{transform:translateX(1px)}}
@keyframes sweep{0%{transform:translate(0,0)}25%{transform:translate(2px,-1px)}50%{transform:translate(3px,1px)}75%{transform:translate(1px,2px)}}
"""

if __name__ == "__main__":
    main()
