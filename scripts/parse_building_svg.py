#!/usr/bin/env python3
"""
Parse SVG path data → simplified 2D points → JSON for 3D building extrusion.

Usage:
    python3 scripts/parse_building_svg.py

Reads the first path (silhouette) from an SVG, flattens Bézier curves,
simplifies with Douglas-Peucker, normalizes coordinates, and outputs JSON.
"""

import json
import math
import re
import xml.etree.ElementTree as ET
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUILDINGS_DIR = Path(__file__).resolve().parent / "buildings"


# ---------------------------------------------------------------------------
# SVG path parsing
# ---------------------------------------------------------------------------
def tokenize_svg_path(d):
    """Tokenize SVG path d attribute into commands + coordinates."""
    tokens = re.findall(r'[MmLlCcSsQqTtAaZz]|[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?', d)
    return tokens


def parse_svg_path(d):
    """Parse SVG path d attribute into a list of subpaths (list of (x,y) points).

    Supports M, L, C, Z commands (absolute only, which matches the Elogio SVG).
    Bézier curves are sampled at regular intervals.
    """
    tokens = tokenize_svg_path(d)
    subpaths = []
    current_path = []
    x, y = 0.0, 0.0
    i = 0

    while i < len(tokens):
        cmd = tokens[i]
        i += 1

        if cmd == 'M':
            if current_path:
                subpaths.append(current_path)
            x, y = float(tokens[i]), float(tokens[i + 1])
            i += 2
            current_path = [(x, y)]
            # Implicit L after M
            while i < len(tokens) and tokens[i] not in 'MmLlCcSsQqTtAaZz':
                x, y = float(tokens[i]), float(tokens[i + 1])
                i += 2
                current_path.append((x, y))

        elif cmd == 'L':
            while i < len(tokens) and tokens[i] not in 'MmLlCcSsQqTtAaZz':
                x, y = float(tokens[i]), float(tokens[i + 1])
                i += 2
                current_path.append((x, y))

        elif cmd == 'C':
            while i < len(tokens) and tokens[i] not in 'MmLlCcSsQqTtAaZz':
                x1, y1 = float(tokens[i]), float(tokens[i + 1])
                x2, y2 = float(tokens[i + 2]), float(tokens[i + 3])
                x3, y3 = float(tokens[i + 4]), float(tokens[i + 5])
                i += 6
                # Sample cubic Bézier
                samples = sample_cubic_bezier(x, y, x1, y1, x2, y2, x3, y3, n=8)
                current_path.extend(samples[1:])  # skip first (= current point)
                x, y = x3, y3

        elif cmd in ('Z', 'z'):
            if current_path:
                # Close path
                current_path.append(current_path[0])
                subpaths.append(current_path)
                current_path = []

        elif cmd == 'm':
            if current_path:
                subpaths.append(current_path)
            dx, dy = float(tokens[i]), float(tokens[i + 1])
            x, y = x + dx, y + dy
            i += 2
            current_path = [(x, y)]

        elif cmd == 'l':
            while i < len(tokens) and tokens[i] not in 'MmLlCcSsQqTtAaZz':
                dx, dy = float(tokens[i]), float(tokens[i + 1])
                x, y = x + dx, y + dy
                i += 2
                current_path.append((x, y))

        elif cmd == 'c':
            while i < len(tokens) and tokens[i] not in 'MmLlCcSsQqTtAaZz':
                dx1, dy1 = float(tokens[i]), float(tokens[i + 1])
                dx2, dy2 = float(tokens[i + 2]), float(tokens[i + 3])
                dx3, dy3 = float(tokens[i + 4]), float(tokens[i + 5])
                i += 6
                x1, y1 = x + dx1, y + dy1
                x2, y2 = x + dx2, y + dy2
                x3, y3 = x + dx3, y + dy3
                samples = sample_cubic_bezier(x, y, x1, y1, x2, y2, x3, y3, n=8)
                current_path.extend(samples[1:])
                x, y = x3, y3

        else:
            # Skip unsupported commands
            pass

    if current_path:
        subpaths.append(current_path)

    return subpaths


def sample_cubic_bezier(x0, y0, x1, y1, x2, y2, x3, y3, n=8):
    """Sample n+1 points along a cubic Bézier curve."""
    points = []
    for i in range(n + 1):
        t = i / n
        t2 = t * t
        t3 = t2 * t
        mt = 1 - t
        mt2 = mt * mt
        mt3 = mt2 * mt
        px = mt3 * x0 + 3 * mt2 * t * x1 + 3 * mt * t2 * x2 + t3 * x3
        py = mt3 * y0 + 3 * mt2 * t * y1 + 3 * mt * t2 * y2 + t3 * y3
        points.append((px, py))
    return points


# ---------------------------------------------------------------------------
# Douglas-Peucker simplification
# ---------------------------------------------------------------------------
def perpendicular_distance(px, py, x1, y1, x2, y2):
    """Perpendicular distance from point (px,py) to line segment (x1,y1)-(x2,y2)."""
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - x1, py - y1)
    t = max(0, min(1, ((px - x1) * dx + (py - y1) * dy) / length_sq))
    proj_x = x1 + t * dx
    proj_y = y1 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


def douglas_peucker(points, tolerance):
    """Simplify a polyline using the Douglas-Peucker algorithm."""
    if len(points) <= 2:
        return points

    # Find the point with maximum distance from the line between first and last
    max_dist = 0
    max_idx = 0
    x1, y1 = points[0]
    x2, y2 = points[-1]

    for i in range(1, len(points) - 1):
        d = perpendicular_distance(points[i][0], points[i][1], x1, y1, x2, y2)
        if d > max_dist:
            max_dist = d
            max_idx = i

    if max_dist > tolerance:
        left = douglas_peucker(points[:max_idx + 1], tolerance)
        right = douglas_peucker(points[max_idx:], tolerance)
        return left[:-1] + right
    else:
        return [points[0], points[-1]]


# ---------------------------------------------------------------------------
# Normalize and center
# ---------------------------------------------------------------------------
def normalize_points(points, target_height=0.4):
    """Center on (0,0), scale to target height, flip Y (SVG Y↓ → Three.js Y↑)."""
    if not points:
        return points

    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    cx = (min_x + max_x) / 2
    cy = (min_y + max_y) / 2
    width = max_x - min_x
    height = max_y - min_y

    # Scale to fit target_height (height-based since it's a sculpture)
    scale = target_height / max(width, height) if max(width, height) > 0 else 1.0

    result = []
    for x, y in points:
        nx = (x - cx) * scale
        ny = -(y - cy) * scale  # flip Y
        result.append((round(nx, 4), round(ny, 4)))

    return result


# ---------------------------------------------------------------------------
# Main: Elogio del Horizonte
# ---------------------------------------------------------------------------
def parse_elogio():
    """Parse El Elogio del Horizonte SVG and output simplified JSON."""
    svg_path = PROJECT_ROOT / "app" / "static" / "images" / "Elogio.svg"

    print(f"Reading {svg_path}...")
    tree = ET.parse(svg_path)
    root = tree.getroot()

    # Find all path elements (handle namespace)
    ns = {'svg': 'http://www.w3.org/2000/svg'}
    paths = root.findall('.//svg:path', ns)
    if not paths:
        paths = root.findall('.//path')

    print(f"Found {len(paths)} paths")

    # Use first path (dark silhouette, 68 commands)
    d = paths[0].get('d', '')
    fill = paths[0].get('fill', 'none')
    print(f"Path 0: fill={fill}, d length={len(d)}")

    # Parse path into subpaths
    subpaths = parse_svg_path(d)
    print(f"Parsed {len(subpaths)} subpaths")
    for i, sp in enumerate(subpaths):
        print(f"  Subpath {i}: {len(sp)} points")

    # Use the largest subpath (main silhouette contour)
    main_subpath = max(subpaths, key=len)
    print(f"Using largest subpath: {len(main_subpath)} points")

    # Simplify with Douglas-Peucker
    tolerance = 3.0  # pixels - adjust for desired detail level
    simplified = douglas_peucker(main_subpath, tolerance)
    print(f"Simplified: {len(main_subpath)} → {len(simplified)} points (tolerance={tolerance})")

    # Normalize: center on (0,0), scale to ~0.15 units, flip Y
    normalized = normalize_points(simplified, target_height=0.15)
    print(f"Normalized to target height 0.15 units")

    # Build output JSON
    output = {
        "name": "Elogio del Horizonte",
        "points": normalized,
        "extrudeDepth": 0.03,
        "color": "0x6b6b69",
        "concejoPolygon": "c013",
        "offsetX": 0.05,
        "offsetZ": 0.20,
    }

    # Save
    BUILDINGS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = BUILDINGS_DIR / "elogio.json"
    out_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    print(f"\nSaved to {out_path}")
    print(f"Points: {len(normalized)}")

    # Print a few sample points for verification
    print("\nFirst 5 points:")
    for p in normalized[:5]:
        print(f"  ({p[0]}, {p[1]})")
    print(f"Last point: ({normalized[-1][0]}, {normalized[-1][1]})")


if __name__ == "__main__":
    parse_elogio()
