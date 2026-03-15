#!/usr/bin/env python3
"""
Extract the Elogio del Horizonte silhouette from SVG via rasterization + scanline tracing.

SVG structure:
  Path 0: rgb(36,25,14) - dark brown (main sculpture)
  Path 1: rgb(155,122,87) - medium brown (highlights)
  Path 2: rgb(181,148,111) - light brown (more highlights)
  Path 3: rgb(254,254,254) - white background

Strategy: rasterize, threshold non-white pixels as sculpture, trace outer + hole.
"""

import json
import io
import numpy as np
from PIL import Image
import cairosvg

SVG_PATH = "app/static/images/Elogio.svg"
OUTPUT_PATH = "scripts/buildings/elogio2.json"
RENDER_HEIGHT = 800  # px for rasterization
TARGET_HEIGHT = 0.06  # 3D units


def douglas_peucker(points, epsilon):
    """Simplify a polyline using Douglas-Peucker algorithm."""
    if len(points) <= 2:
        return points

    start, end = np.array(points[0], dtype=float), np.array(points[-1], dtype=float)
    line_vec = end - start
    line_len = np.linalg.norm(line_vec)

    if line_len < 1e-10:
        dists = [np.linalg.norm(np.array(p, dtype=float) - start) for p in points]
        max_idx = int(np.argmax(dists))
        max_dist = dists[max_idx]
    else:
        line_unit = line_vec / line_len
        dists = []
        for p in points:
            v = np.array(p, dtype=float) - start
            proj = np.dot(v, line_unit)
            proj = max(0.0, min(float(line_len), float(proj)))
            closest = start + proj * line_unit
            dists.append(float(np.linalg.norm(np.array(p, dtype=float) - closest)))
        max_idx = int(np.argmax(dists))
        max_dist = dists[max_idx]

    if max_dist > epsilon:
        left = douglas_peucker(points[:max_idx + 1], epsilon)
        right = douglas_peucker(points[max_idx:], epsilon)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


def main():
    # 1. Rasterize SVG
    print("Rasterizing SVG...")
    png_data = cairosvg.svg2png(url=SVG_PATH, output_height=RENDER_HEIGHT)
    img = Image.open(io.BytesIO(png_data)).convert("RGB")
    w, h = img.size
    print(f"  Rasterized: {w}x{h}")

    # 2. Create mask: non-white pixels = sculpture
    pixels = np.array(img)
    # White threshold: all channels > 240
    is_white = np.all(pixels > 240, axis=2)
    mask = (~is_white).astype(np.uint8)

    # Find bounding box
    rows = np.any(mask, axis=1)
    cols = np.any(mask, axis=0)
    y_min, y_max = int(np.where(rows)[0][0]), int(np.where(rows)[0][-1])
    x_min, x_max = int(np.where(cols)[0][0]), int(np.where(cols)[0][-1])
    print(f"  Content bbox: x=[{x_min},{x_max}], y=[{y_min},{y_max}], size={x_max-x_min}x{y_max-y_min}")

    # 3. Scanline analysis
    print("Scanline analysis...")
    outer_left = []
    outer_right = []
    hole_right_of_left = []
    hole_left_of_right = []
    hole_rows = []

    for y in range(y_min, y_max + 1):
        row = mask[y, :]
        filled = np.where(row > 0)[0]
        if len(filled) == 0:
            continue

        left = int(filled[0])
        right = int(filled[-1])
        outer_left.append((left, y))
        outer_right.append((right, y))

        # Check for gaps (holes between runs)
        diffs = np.diff(filled)
        gaps = np.where(diffs > 5)[0]  # min gap of 5px

        if len(gaps) >= 1:
            # Take the largest gap
            gap_info = [(int(diffs[g]), g) for g in gaps]
            gap_info.sort(reverse=True)
            biggest_gap_idx = gap_info[0][1]
            gap_size = gap_info[0][0]

            left_run_end = int(filled[biggest_gap_idx])
            right_run_start = int(filled[biggest_gap_idx + 1])
            hole_right_of_left.append((left_run_end, y))
            hole_left_of_right.append((right_run_start, y))
            hole_rows.append(y)

    print(f"  Outer: {len(outer_left)} rows")
    print(f"  Hole rows: {len(hole_rows)}")
    if hole_rows:
        print(f"  Hole y range: {min(hole_rows)}-{max(hole_rows)}")

    # 4. Build outer contour (down left side, up right side)
    outer_contour = list(outer_left) + list(reversed(outer_right))

    # 5. Build hole contour (down right-of-left, up left-of-right)
    hole_contour = []
    if hole_rows:
        hole_contour = list(hole_right_of_left) + list(reversed(hole_left_of_right))

    # 6. Simplify
    outer_eps = 4.0
    hole_eps = 5.0

    outer_simplified = douglas_peucker(outer_contour, outer_eps)
    print(f"  Outer simplified: {len(outer_contour)} -> {len(outer_simplified)} points (eps={outer_eps})")

    hole_simplified = []
    if hole_contour:
        hole_simplified = douglas_peucker(hole_contour, hole_eps)
        print(f"  Hole simplified: {len(hole_contour)} -> {len(hole_simplified)} points (eps={hole_eps})")

    # 7. Normalize: flip Y, center, scale to TARGET_HEIGHT
    ref_pts = outer_simplified + (hole_simplified if hole_simplified else [])
    all_x = [p[0] for p in ref_pts]
    all_y = [p[1] for p in ref_pts]

    cx = (min(all_x) + max(all_x)) / 2
    cy = (min(all_y) + max(all_y)) / 2
    pixel_height = max(all_y) - min(all_y)
    pixel_width = max(all_x) - min(all_x)
    scale = TARGET_HEIGHT / pixel_height

    print(f"  Pixel size: {pixel_width:.0f}x{pixel_height:.0f}")
    print(f"  Scale: {scale:.6f}, 3D size: {pixel_width*scale:.4f} x {TARGET_HEIGHT}")

    def norm(px, py):
        x = round((px - cx) * scale, 5)
        y = round(-(py - cy) * scale, 5)  # flip Y
        return [x, y]

    outer_norm = [norm(p[0], p[1]) for p in outer_simplified]
    hole_norm = [norm(p[0], p[1]) for p in hole_simplified] if hole_simplified else []

    # 8. ASCII preview
    def ascii_preview(points, label, w=70, h=30):
        px = [p[0] for p in points]
        py = [p[1] for p in points]
        # Use outer bounds for consistent framing
        ox = [p[0] for p in outer_norm]
        oy = [p[1] for p in outer_norm]
        xr = max(ox) - min(ox)
        yr = max(oy) - min(oy)
        if xr == 0 or yr == 0:
            return

        grid = [[' '] * w for _ in range(h)]
        for i in range(len(points)):
            p1 = points[i]
            p2 = points[(i + 1) % len(points)]
            c1 = int((p1[0] - min(ox)) / xr * (w - 1))
            r1 = int((1 - (p1[1] - min(oy)) / yr) * (h - 1))
            c2 = int((p2[0] - min(ox)) / xr * (w - 1))
            r2 = int((1 - (p2[1] - min(oy)) / yr) * (h - 1))
            steps = max(abs(c2 - c1), abs(r2 - r1), 1)
            for s in range(steps + 1):
                t = s / steps
                c = int(c1 + t * (c2 - c1))
                r = int(r1 + t * (r2 - r1))
                c = max(0, min(w - 1, c))
                r = max(0, min(h - 1, r))
                grid[r][c] = '#'

        print(f"\n  {label}:")
        for row in grid:
            print("  " + "".join(row))

    ascii_preview(outer_norm, "Outer contour")
    if hole_norm:
        ascii_preview(hole_norm, "Hole contour")

    # 9. Write JSON
    result = {
        "name": "Elogio 2D",
        "type": "extrude",
        "outer": outer_norm,
        "holes": [hole_norm] if hole_norm else [],
        "extrudeDepth": 0.015,
        "color": "0x8a8a88",
        "concejoPolygon": "c013",
        "offsetX": 0.05,
        "offsetZ": 0.10,
        "rotateX": "-Math.PI / 2",
        "rotateY": "Math.PI"
    }

    with open(OUTPUT_PATH, 'w') as f:
        json.dump(result, f, indent=2)

    print(f"\n  Written to {OUTPUT_PATH}")
    print(f"  Outer: {len(outer_norm)} points, Holes: {len(result['holes'])}")
    if hole_norm:
        print(f"  Hole 0: {len(hole_norm)} points")


if __name__ == "__main__":
    main()
