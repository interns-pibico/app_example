#!/usr/bin/env python3
"""
Build script: transforms asturias_project/scene.js into app/static/js/asturias-scene.js

Performs:
- Import path replacement (./vendor/ -> /static/vendor/three/)
- Background color change (0x1a6b8a -> 0xa7d1f1)
- Material color replacement with 8-color pastel palette (random, seed 42)
- Extrusion depth reduction (25%)
- Marker position replacement using polygon centroids (not GPS)
- Marker geometry shrink (~63%)
- Raycaster fix for embedded container (not full viewport)
- Top-down camera (drone view) + disable orbit rotation
- Orphan polygon handling (color matching + hiding degenerate)
- UFO platform interactivity (click polygon → rise + scale + drift to center)
- 3D buildings on platforms (appear when platform rises)
- Ocean with animated waves + low-poly fishing boats (Cantabrian Sea)
"""

import json
import random
import re
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment

PROJECT_ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------------------
# Color palette (8 pastel colors, assigned randomly with fixed seed)
# ---------------------------------------------------------------------------
PASTEL_PALETTE = [
    "#F79887", "#F7B192", "#F2FDFF", "#EDECE8",
    "#E6D7B8", "#E2D6E8", "#F6F0E0", "#DE9F63",
]

# Orphan polygons: SVG fragments/artifacts not matched by Hungarian algorithm
# parent=None means degenerate (hide), otherwise match color to parent polygon
ORPHAN_POLYGONS = {
    34: {"parent": 31, "name": "Navia"},
    45: {"parent": 63, "name": "Cangas del Narcea"},
    74: {"parent": None, "name": None},  # degenerate SVG artifact - hide
    80: {"parent": 79, "name": "Ibias"},
}

# Ocean and boats configuration
OCEAN_Z = 2.72  # Center Z of ocean plane (slightly overlaps coast at Z≈1.47)

BOAT_CONFIGS = [
    {"id": "boat0", "x": -3.5, "z": 2.00, "rotY": "-Math.PI/2",  "hull": "0xc4713b", "sail": "0xf2fdff", "scale": 1.0,  "phase": 0.0, "speed":  0.003},
    {"id": "boat1", "x":  2.0, "z": 2.15, "rotY": "Math.PI/2",   "hull": "0x6b8fa3", "sail": "0xf6f0e0", "scale": 0.85, "phase": 1.5, "speed": -0.002},
    {"id": "boat2", "x":  4.5, "z": 1.95, "rotY": "-Math.PI/2",  "hull": "0x8b6b4a", "sail": "0xedece8", "scale": 1.1,  "phase": 3.0, "speed":  0.0035},
    {"id": "boat3", "x": -1.0, "z": 2.25, "rotY": "Math.PI/2",   "hull": "0xc4713b", "sail": "0xe2d6e8", "scale": 0.75, "phase": 4.5, "speed": -0.002},
]


def hex_css_to_threejs(hex_color):
    """Convert '#RRGGBB' to '0xrrggbb'."""
    return "0x" + hex_color.lstrip("#").lower()


# ---------------------------------------------------------------------------
# Polygon data extraction
# ---------------------------------------------------------------------------
def extract_polygon_data(content):
    """Parse obj_cNNN_pts arrays and their ExtrudeGeometry depth values.

    Returns dict: polygon_index -> {points: [[x,y],...], depth: float}
    """
    polygon_data = {}

    # Extract point arrays: const obj_cNNN_pts = [[x,y], ...];
    pts_re = re.compile(
        r"const obj_c(\d{3})_pts\s*=\s*\[(.*?)\];", re.DOTALL
    )
    for m in pts_re.finditer(content):
        idx = int(m.group(1))
        raw = m.group(2).strip()
        # Parse nested arrays [[x,y],[x,y],...]
        points = []
        pair_re = re.compile(r"\[(-?[\d.eE+-]+),\s*(-?[\d.eE+-]+)\]")
        for pair in pair_re.finditer(raw):
            points.append((float(pair.group(1)), float(pair.group(2))))
        polygon_data[idx] = {"points": points, "depth": 0.0}

    # Extract depth values: ExtrudeGeometry(obj_cNNN_shape, { depth: VALUE, ...})
    depth_re = re.compile(
        r"ExtrudeGeometry\(obj_c(\d{3})_shape,\s*\{\s*depth:\s*(-?[\d.eE+-]+)"
    )
    for m in depth_re.finditer(content):
        idx = int(m.group(1))
        if idx in polygon_data:
            polygon_data[idx]["depth"] = float(m.group(2))

    return polygon_data


def compute_centroid(points):
    """Compute 2D centroid (mean of vertices)."""
    if not points:
        return 0.0, 0.0
    cx = sum(p[0] for p in points) / len(points)
    cy = sum(p[1] for p in points) / len(points)
    return cx, cy


# ---------------------------------------------------------------------------
# Compute COAST_POINTS dynamically from real polygon vertices
# ---------------------------------------------------------------------------
def _point_in_polygon(px, pz, verts):
    """Ray-casting point-in-polygon test in XZ plane."""
    n = len(verts)
    inside = False
    j = n - 1
    for i in range(n):
        xi, zi = verts[i]
        xj, zj = verts[j]
        if ((zi > pz) != (zj > pz)) and (px < (xj - xi) * (pz - zi) / (zj - zi) + xi):
            inside = not inside
        j = i
    return inside


def compute_coast_from_polygons(polygon_data):
    """Extract COAST_POINTS from sea-facing outer edges of all map polygons.

    Algorithm:
      For each polygon edge, compute the outward normal (away from centroid).
      If the normal has a northward component AND the midpoint slightly north
      of the edge is NOT inside any other polygon, the edge faces the sea.
      Collect those edge endpoints, sample at regular X intervals.

    Transform: world_X = pts_x (NO negation), world_Z = -pts_y
    No Z-value thresholds — works for any polygon regardless of altitude.

    Returns a list of [x, z] pairs for use as COAST_POINTS in JS:
        const COAST_POINTS = <result>.sort((a,b)=>a[0]-b[0]);
    """
    # Build world-coord vertex lists for all polygons
    poly_world = {}
    for poly_id, pdata in polygon_data.items():
        pts = pdata["points"]
        poly_world[poly_id] = [(p[0], -p[1]) for p in pts]  # world_X=pts_x, world_Z=-pts_y

    sea_facing_pts = []
    PROBE_DIST = 0.06   # probe this far north of edge midpoint
    NORTH_THR  = 0.25   # minimum outward-normal Z component (filters E/W-facing edges)

    for poly_id, verts in poly_world.items():
        n = len(verts)
        if n < 3:
            continue
        cx = sum(x for x, z in verts) / n
        cz = sum(z for x, z in verts) / n

        for i in range(n):
            v1 = verts[i]
            v2 = verts[(i + 1) % n]
            mx = (v1[0] + v2[0]) / 2
            mz = (v1[1] + v2[1]) / 2

            # Edge direction vector
            dx = v2[0] - v1[0]
            dz = v2[1] - v1[1]

            # Two perpendicular candidates
            nx1, nz1 =  dz, -dx
            nx2, nz2 = -dz,  dx

            # Outward normal: points AWAY from centroid
            to_x, to_z = mx - cx, mz - cz
            if nx1 * to_x + nz1 * to_z >= 0:
                out_nx, out_nz = nx1, nz1
            else:
                out_nx, out_nz = nx2, nz2

            # Normalize
            mag = (out_nx ** 2 + out_nz ** 2) ** 0.5
            if mag < 1e-9:
                continue
            out_nx /= mag
            out_nz /= mag

            # Must face northward
            if out_nz <= NORTH_THR:
                continue

            # Probe slightly north of edge midpoint
            probe_x = mx + out_nx * PROBE_DIST
            probe_z = mz + out_nz * PROBE_DIST

            # Skip if probe is inside the current polygon (inward-pointing normal)
            if _point_in_polygon(probe_x, probe_z, verts):
                continue

            # Sea-facing = probe is NOT inside any other polygon
            in_other = any(
                other_id != poly_id and _point_in_polygon(probe_x, probe_z, other_verts)
                for other_id, other_verts in poly_world.items()
            )
            if not in_other:
                sea_facing_pts.append(v1)
                sea_facing_pts.append(v2)

    if not sea_facing_pts:
        print("  WARNING: No sea-facing edges found, using fallback COAST_POINTS")
        return [[-7.2, 1.15], [7.2, 1.15]]

    sea_facing_pts.sort(key=lambda v: v[0])
    x_min = sea_facing_pts[0][0]
    x_max = sea_facing_pts[-1][0]

    # Sample at 0.05 unit intervals, search window ±0.12, take max Z (northernmost)
    coast_pts = []
    x = x_min
    while x <= x_max + 0.001:
        nearby_z = [z for vx, z in sea_facing_pts if abs(vx - x) <= 0.12]
        if nearby_z:
            coast_pts.append([round(x, 3), round(max(nearby_z), 4)])
        x = round(x + 0.05, 6)

    if not coast_pts:
        return [[-7.2, 1.15], [7.2, 1.15]]

    # Truncate at first abrupt Z drop going westward (submerged polygons west of Castropol).
    # coast_pts is sorted by X ascending; going westward = toward higher index (higher X).
    # In the western region (X > 4.0), a drop > 0.25 Z in one step signals submerged polygons.
    clean_pts = [coast_pts[0]]
    for i in range(1, len(coast_pts)):
        curr_x, curr_z = coast_pts[i]
        prev_z = clean_pts[-1][1]
        if curr_x > 4.0 and curr_z < prev_z - 0.25:
            break
        clean_pts.append([curr_x, curr_z])
    coast_pts = clean_pts

    # Push ocean boundary slightly south (into polygon) to hide coast cliff and beach zone.
    # This ensures the breaking-wave coastFactor effect and beach strip are covered by the
    # polygon geometry, eliminating visible sand and edge artifacts during wave animation.
    Z_OVERLAP = 0.04
    coast_pts = [[x, round(z - Z_OVERLAP, 4)] for x, z in coast_pts]

    # Sentinel points at ocean extremes carry the Z of the nearest computed point
    coast_pts = [[-7.2, coast_pts[0][1]]] + coast_pts + [[7.2, coast_pts[-1][1]]]

    print(f"  Sea-facing vertices: {len(sea_facing_pts)}, sampled coast points: {len(coast_pts)}")
    return coast_pts


def extract_marker_names(content):
    """Extract concejo names from marker userData."""
    name_re = re.compile(r'm(\d+)g\.userData=(\{.*?\});')
    names = {}
    for m in name_re.finditer(content):
        idx = int(m.group(1))
        try:
            data = json.loads(m.group(2))
            names[idx] = data.get("name", f"m{idx}")
        except json.JSONDecodeError:
            pass
    return names


# ---------------------------------------------------------------------------
# Marker-to-polygon matching by GPS proximity (Hungarian algorithm)
# ---------------------------------------------------------------------------
def build_marker_polygon_mapping(content, polygon_data):
    """Match markers to polygons using GPS proximity, not index.

    Markers are ordered alphabetically by concejo name, but polygons are
    ordered by SVG appearance. This function:
    1. Parses original marker positions (GPS-derived) from the source
    2. Converts 3D positions to 2D polygon space
    3. Computes centroids of all polygons
    4. Uses Hungarian algorithm for optimal global matching

    Returns: dict mapping marker_index -> polygon_index
    """
    # 1. Parse original marker pole positions: mKp.position.set(X, Y, Z)
    marker_pos = {}  # marker_idx -> (x_3d, z_3d)
    pos_re = re.compile(
        r"m(\d+)p\.position\.set\("
        r"(-?[\d.eE+-]+),(-?[\d.eE+-]+),(-?[\d.eE+-]+)\)"
    )
    for m in pos_re.finditer(content):
        idx = int(m.group(1))
        x_3d = float(m.group(2))
        z_3d = float(m.group(4))
        marker_pos[idx] = (x_3d, z_3d)

    # 2. Convert marker 3D positions to 2D polygon space
    #    Transform: pts_x = X_3d, pts_y = -Z_3d
    marker_2d = {}
    for idx, (x3, z3) in marker_pos.items():
        marker_2d[idx] = (x3, -z3)

    # 3. Compute centroids for all polygons
    poly_centroids = {}
    for pidx, pdata in polygon_data.items():
        poly_centroids[pidx] = compute_centroid(pdata["points"])

    # 4. Build distance matrix and solve with Hungarian algorithm
    marker_indices = sorted(marker_2d.keys())
    poly_indices = sorted(poly_centroids.keys())

    n_markers = len(marker_indices)
    n_polys = len(poly_indices)

    cost_matrix = np.zeros((n_markers, n_polys))
    for i, midx in enumerate(marker_indices):
        mx, my = marker_2d[midx]
        for j, pidx in enumerate(poly_indices):
            px, py = poly_centroids[pidx]
            cost_matrix[i, j] = (mx - px) ** 2 + (my - py) ** 2

    row_ind, col_ind = linear_sum_assignment(cost_matrix)

    mapping = {}
    total_dist = 0.0
    for r, c in zip(row_ind, col_ind):
        midx = marker_indices[r]
        pidx = poly_indices[c]
        dist = np.sqrt(cost_matrix[r, c])
        total_dist += dist
        mapping[midx] = pidx

    avg_dist = total_dist / len(mapping) if mapping else 0
    print(f"  Matched {len(mapping)} markers to polygons (avg distance: {avg_dist:.4f})")

    # 5. Report a few matches for verification
    marker_names = extract_marker_names(content)

    samples = list(mapping.items())[:5]
    for midx, pidx in samples:
        name = marker_names.get(midx, f"m{midx}")
        print(f"    m{midx} ({name}) -> polygon c{pidx:03d}")

    return mapping


# ---------------------------------------------------------------------------
# Marker position replacement using polygon centroids
# ---------------------------------------------------------------------------
def replace_marker_positions_with_centroids(content, polygon_data, mapping=None):
    """Replace marker positions with centroids of matched polygons.

    Uses proximity-based mapping (Hungarian algorithm) to correctly match
    each marker to its polygon, rather than assuming mK -> obj_cK.
    After rotateX(-PI/2): pts_x -> X_3d, pts_y -> -Z_3d, depth -> Y_3d.
    """
    # Build correct mapping first
    if mapping is None:
        mapping = build_marker_polygon_mapping(content, polygon_data)

    lines = content.split("\n")
    pos_re = re.compile(
        r"^(.*m(\d+)([pbg])\.position\.set\()"
        r"(-?[\d.eE+-]+),(-?[\d.eE+-]+),(-?[\d.eE+-]+)"
        r"(\).*)$"
    )

    replaced = 0
    missing = set()
    for i, line in enumerate(lines):
        m = pos_re.match(line)
        if not m:
            continue
        prefix = m.group(1)
        idx = int(m.group(2))
        part = m.group(3)  # p=pole, b=bulb, g=glow
        postfix = m.group(7)

        if idx not in mapping:
            missing.add(idx)
            continue

        poly_idx = mapping[idx]
        pd = polygon_data[poly_idx]
        cx, cy = compute_centroid(pd["points"])
        depth = pd["depth"]

        # Transform: pts_x -> X, pts_y -> -Z (due to rotateX(-PI/2))
        x_3d = round(cx, 4)
        z_3d = round(-cy, 4)

        # Y position based on depth + offset
        if part == "p":  # pole
            y_3d = round(depth + 0.10, 4)
        else:  # bulb or glow
            y_3d = round(depth + 0.20, 4)

        lines[i] = f"{prefix}{x_3d},{y_3d},{z_3d}{postfix}"
        replaced += 1

    if missing:
        print(f"  Warning: {len(missing)} markers without matching polygon: {sorted(missing)}")
    print(f"  Replaced {replaced} marker position lines")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Fix raycaster for embedded container (not full viewport)
# ---------------------------------------------------------------------------
def fix_raycaster(content):
    """Replace window.innerWidth/Height with container bounding rect."""
    # Click handler
    old_click = (
        "renderer.domElement.addEventListener('click', (e) => {\n"
        "    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;\n"
        "    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;"
    )
    new_click = (
        "renderer.domElement.addEventListener('click', (e) => {\n"
        "    const rect = renderer.domElement.getBoundingClientRect();\n"
        "    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;\n"
        "    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;"
    )
    content = content.replace(old_click, new_click)

    # Mousemove handler
    old_move = (
        "renderer.domElement.addEventListener('mousemove', (e) => {\n"
        "    mouse.x = (e.clientX / window.innerWidth) * 2 - 1;\n"
        "    mouse.y = -(e.clientY / window.innerHeight) * 2 + 1;"
    )
    new_move = (
        "renderer.domElement.addEventListener('mousemove', (e) => {\n"
        "    const rect = renderer.domElement.getBoundingClientRect();\n"
        "    mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;\n"
        "    mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;"
    )
    content = content.replace(old_move, new_move)
    return content


# ---------------------------------------------------------------------------
# Text labels (CSS2DRenderer)
# ---------------------------------------------------------------------------
def inject_text_labels(content, polygon_data):
    """Inject CSS2DRenderer labels for each marker with userData.

    Parses marker glow meshes (mKg) to extract name and position,
    then injects:
    - CSS2DRenderer import at top
    - Label creation + labelRenderer setup before animate()
    - labelRenderer.render() in animate loop
    - labelRenderer.setSize() in resize handler
    """
    # 1. Extract marker names and positions from glow meshes
    #    Pattern: mKg.position.set(X,Y,Z);
    #    followed by: mKg.userData={"name": "...", ...};
    markers = {}  # idx -> {name, x, y, z}
    pos_re = re.compile(
        r"m(\d+)g\.position\.set\((-?[\d.eE+-]+),(-?[\d.eE+-]+),(-?[\d.eE+-]+)\)"
    )
    name_re = re.compile(r'm(\d+)g\.userData=(\{.*?\});')

    for m in pos_re.finditer(content):
        idx = int(m.group(1))
        markers.setdefault(idx, {})
        markers[idx]["x"] = m.group(2)
        markers[idx]["y"] = m.group(3)
        markers[idx]["z"] = m.group(4)

    for m in name_re.finditer(content):
        idx = int(m.group(1))
        try:
            data = json.loads(m.group(2))
            markers.setdefault(idx, {})
            markers[idx]["name"] = data.get("name", f"c{idx}")
        except json.JSONDecodeError:
            pass

    # Filter to only markers with both name and position
    valid = {k: v for k, v in markers.items() if "name" in v and "x" in v}
    print(f"  Found {len(valid)} markers with names")

    # 2. Add CSS2DRenderer import after OrbitControls import
    content = content.replace(
        "import { OrbitControls } from '/static/vendor/three/OrbitControls.js';",
        "import { OrbitControls } from '/static/vendor/three/OrbitControls.js';\n"
        "import { CSS2DRenderer, CSS2DObject } from '/static/vendor/three/CSS2DRenderer.js';",
    )

    # 3. Build label code block
    label_lines = [
        "",
        "// --- Text labels (CSS2DRenderer) ---",
        "const labelRenderer = new CSS2DRenderer();",
        "labelRenderer.setSize(container.clientWidth, container.clientHeight);",
        "labelRenderer.domElement.style.position = 'absolute';",
        "labelRenderer.domElement.style.top = '0';",
        "labelRenderer.domElement.style.pointerEvents = 'none';",
        "container.appendChild(labelRenderer.domElement);",
        "",
    ]

    for idx in sorted(valid.keys()):
        m = valid[idx]
        name_escaped = m["name"].replace("'", "\\'")
        # Place label slightly above the bulb
        y_offset = round(float(m["y"]) + 0.05, 4)
        label_lines.append(
            f"const lbl_{idx} = document.createElement('div');"
        )
        label_lines.append(f"lbl_{idx}.className = 'label-3d';")
        label_lines.append(f"lbl_{idx}.textContent = '{name_escaped}';")
        label_lines.append(
            f"const lblObj_{idx} = new CSS2DObject(lbl_{idx});"
        )
        label_lines.append(
            f"lblObj_{idx}.position.set({m['x']}, {y_offset}, {m['z']});"
        )
        label_lines.append(f"scene.add(lblObj_{idx});")

    label_block = "\n".join(label_lines)

    # 4. Insert label block just before animate()
    content = content.replace(
        "// Animation with pulse\n",
        label_block + "\n\n// Animation with pulse\n",
    )

    # 5. Add labelRenderer.render() in animate loop
    content = content.replace(
        "    renderer.render(scene, camera);\n}",
        "    renderer.render(scene, camera);\n"
        "    labelRenderer.render(scene, camera);\n}",
    )

    # 6. Add labelRenderer.setSize() in resize handler
    content = content.replace(
        "    renderer.setSize(w, h);\n});",
        "    renderer.setSize(w, h);\n"
        "    labelRenderer.setSize(w, h);\n});",
    )

    return content


# ---------------------------------------------------------------------------
# Quarter extrusion depths
# ---------------------------------------------------------------------------
def quarter_extrusion_depths(content):
    """Multiply all ExtrudeGeometry depth values by 0.25."""
    depth_re = re.compile(
        r"(ExtrudeGeometry\(obj_c\d{3}_shape,\s*\{\s*depth:\s*)(-?[\d.eE+-]+)"
    )
    count = [0]

    def _quarter(m):
        depth = float(m.group(2))
        new_depth = depth * 0.25
        count[0] += 1
        return f"{m.group(1)}{new_depth}"

    content = depth_re.sub(_quarter, content)
    print(f"  Quartered {count[0]} depth values")
    return content


# ---------------------------------------------------------------------------
# Shrink marker geometry (~63% size)
# ---------------------------------------------------------------------------
def shrink_marker_geometry(content):
    """Reduce marker pole, bulb and glow sizes by ~63%."""
    count = 0
    # Pole: CylinderGeometry(0.008,0.012,0.3,6) -> (0.005,0.008,0.2,6)
    old_pole = "CylinderGeometry(0.008,0.012,0.3,6)"
    new_pole = "CylinderGeometry(0.005,0.008,0.2,6)"
    n = content.count(old_pole)
    content = content.replace(old_pole, new_pole)
    count += n

    # Bulb: SphereGeometry(0.035,8,8) -> (0.022,8,8)
    old_bulb = "SphereGeometry(0.035,8,8)"
    new_bulb = "SphereGeometry(0.022,8,8)"
    n = content.count(old_bulb)
    content = content.replace(old_bulb, new_bulb)
    count += n

    # Glow: SphereGeometry(0.065,8,8) -> (0.042,8,8)
    old_glow = "SphereGeometry(0.065,8,8)"
    new_glow = "SphereGeometry(0.042,8,8)"
    n = content.count(old_glow)
    content = content.replace(old_glow, new_glow)
    count += n

    print(f"  Shrunk {count} marker geometry instances")
    return content


# ---------------------------------------------------------------------------
# Top-down camera (drone view) + disable orbit rotation
# ---------------------------------------------------------------------------
def add_polygon_doubleside(content):
    """Add THREE.DoubleSide to all polygon MeshLambertMaterial so laterals are visible."""
    mat_re = re.compile(
        r"(const obj_c\d{3}_mat = new THREE\.MeshLambertMaterial\(\{[^}]*?)"
        r"(\s*\})"
    )
    count = [0]

    def _add_side(m):
        # Skip if already has side:
        if "side:" in m.group(1):
            return m.group(0)
        count[0] += 1
        return f"{m.group(1)}, side: THREE.DoubleSide{m.group(2)}"

    content = mat_re.sub(_add_side, content)
    print(f"  Added DoubleSide to {count[0]} polygon materials")
    return content


def set_topdown_camera(content):
    """Set camera to top-down (drone) view looking straight down."""
    content = content.replace(
        "camera.position.set(0, 8, 6)",
        "camera.position.set(0, 12, -0.001)",
    )
    return content


def disable_orbit_rotation(content):
    """Disable orbit rotation, keeping zoom and pan."""
    content = content.replace(
        "controls.dampingFactor = 0.05;",
        "controls.dampingFactor = 0.05;\ncontrols.enableRotate = false;",
    )
    return content


# ---------------------------------------------------------------------------
# Handle orphan polygons
# ---------------------------------------------------------------------------
def handle_orphan_polygons(content):
    """Fix orphan polygon colors to match parent concejo, hide degenerate."""
    # Extract current polygon colors from content
    color_re = re.compile(
        r"const obj_c(\d{3})_mat = new THREE\.MeshLambertMaterial\(\{ color: (0x[0-9a-fA-F]{6})"
    )
    colors = {}
    for m in color_re.finditer(content):
        colors[int(m.group(1))] = m.group(2)

    for orphan_idx, info in ORPHAN_POLYGONS.items():
        parent_idx = info["parent"]
        if parent_idx is not None:
            if parent_idx in colors and orphan_idx in colors:
                # Replace orphan's color with parent's color
                old_mat = (
                    f"obj_c{orphan_idx:03d}_mat = new THREE.MeshLambertMaterial"
                    f"({{ color: {colors[orphan_idx]}"
                )
                new_mat = (
                    f"obj_c{orphan_idx:03d}_mat = new THREE.MeshLambertMaterial"
                    f"({{ color: {colors[parent_idx]}"
                )
                content = content.replace(old_mat, new_mat)
                print(
                    f"  c{orphan_idx:03d}: color {colors[orphan_idx]} -> "
                    f"{colors[parent_idx]} (parent c{parent_idx:03d}, {info['name']})"
                )
        else:
            # Hide degenerate polygon
            old_add = f"scene.add(obj_c{orphan_idx:03d});"
            new_add = (
                f"obj_c{orphan_idx:03d}.visible = false;\n"
                f"scene.add(obj_c{orphan_idx:03d});"
            )
            content = content.replace(old_add, new_add, 1)
            print(f"  c{orphan_idx:03d}: hidden (degenerate SVG artifact)")

    return content


# ---------------------------------------------------------------------------
# Polygon interactivity (click-to-animate + hover)
# ---------------------------------------------------------------------------
def inject_polygon_interactivity(content, polygon_data, mapping, marker_names):
    """Add UFO platform animation: polygon rises, scales to fill viewport, drifts to center.

    Injects:
    - userData.name + centroidX/centroidZ + fillScale on each polygon mesh
    - Polygon array for raycaster
    - animatePolygon() with 3-target lerp (scale, Y, centerWeight)
    - Click handler: expand polygon or collapse on any click when expanded
    - Mousemove handler: pointer cursor when expanded (click-to-close hint)
    - Animation loop with convergence snap
    """
    # 1. Build polygon -> name mapping
    polygon_to_name = {}
    for midx, pidx in mapping.items():
        if midx in marker_names:
            polygon_to_name[pidx] = marker_names[midx]
    # Add orphan polygon names
    for orphan_idx, info in ORPHAN_POLYGONS.items():
        if info["name"]:
            polygon_to_name[orphan_idx] = info["name"]

    print(f"  Named {len(polygon_to_name)} polygons")

    # 2. Build userData assignments (name + centroidX/Z + fillScale) + polygon array
    MAP_WIDTH = 9.6    # X span of the full map
    MAP_HEIGHT = 3.3   # Z span of the full map
    FILL_MARGIN = 0.95 # 95% of viewport (reduced to fit ISO camera frustum)
    MAX_FILL_SCALE = 20.0

    lines = ["", "// --- Polygon userData + interaction array ---"]
    for pidx in sorted(polygon_data.keys()):
        pdata = polygon_data[pidx]
        cx, cy = compute_centroid(pdata["points"])
        # Transform to 3D: pts_x -> X, pts_y -> -Z
        cx_3d = round(cx, 4)
        cz_3d = round(-cy, 4)
        lines.append(f"obj_c{pidx:03d}.userData.centroidX = {cx_3d};")
        lines.append(f"obj_c{pidx:03d}.userData.centroidZ = {cz_3d};")
        name = polygon_to_name.get(pidx)
        if name:
            name_escaped = name.replace("'", "\\'")
            lines.append(f"obj_c{pidx:03d}.userData.name = '{name_escaped}';")
        # Compute fillScale: scale needed for polygon to fill the viewport
        pts = pdata["points"]
        if pts:
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            bbox_w = max(xs) - min(xs)
            bbox_h = max(ys) - min(ys)
            if bbox_w > 0 and bbox_h > 0:
                fill_scale = min(MAP_WIDTH / bbox_w, MAP_HEIGHT / bbox_h) * FILL_MARGIN
                fill_scale = min(fill_scale, MAX_FILL_SCALE)
            else:
                fill_scale = 1.0
        else:
            fill_scale = 1.0
        lines.append(f"obj_c{pidx:03d}.userData.fillScale = {round(fill_scale, 2)};")
        lines.append(f"obj_c{pidx:03d}.userData.depth = {round(pdata['depth'], 6)};")

    # --- Frustum verification for ISO camera ---
    # Verify that every polygon, when expanded by its fillScale at targetY=0.75,
    # fits within the camera frustum. Reduce fillScale if needed.
    CAM_POS = np.array([6.0, 6.0, -6.0])
    CAM_TARGET = np.array([0.0, 0.75, 0.0])
    FOV_DEG = 45.0
    ASPECT = 16.0 / 9.0  # typical widescreen
    NDC_LIMIT = 0.95  # must fit within ±0.95 NDC

    # Build view-projection matrix
    def _build_vp_matrix(cam_pos, cam_target, fov_deg, aspect):
        """Build a view-projection matrix (numpy, no dependencies)."""
        # View matrix (lookAt)
        forward = cam_target - cam_pos
        forward = forward / np.linalg.norm(forward)
        world_up = np.array([0.0, 1.0, 0.0])
        right = np.cross(forward, world_up)
        right = right / np.linalg.norm(right)
        up = np.cross(right, forward)

        view = np.eye(4)
        view[0, :3] = right
        view[1, :3] = up
        view[2, :3] = -forward
        view[0, 3] = -np.dot(right, cam_pos)
        view[1, 3] = -np.dot(up, cam_pos)
        view[2, 3] = np.dot(forward, cam_pos)

        # Projection matrix (perspective)
        fov_rad = np.radians(fov_deg)
        f = 1.0 / np.tan(fov_rad / 2.0)
        near, far = 0.1, 1000.0
        proj = np.zeros((4, 4))
        proj[0, 0] = f / aspect
        proj[1, 1] = f
        proj[2, 2] = -(far + near) / (far - near)
        proj[2, 3] = -2.0 * far * near / (far - near)
        proj[3, 2] = -1.0
        return proj @ view

    vp = _build_vp_matrix(CAM_POS, CAM_TARGET, FOV_DEG, ASPECT)

    def _project_point(vp_mat, x, y, z):
        """Project a 3D point to NDC using the VP matrix."""
        p = vp_mat @ np.array([x, y, z, 1.0])
        if abs(p[3]) < 1e-10:
            return 999.0, 999.0  # degenerate
        return p[0] / p[3], p[1] / p[3]

    adjusted_count = 0
    for pidx in sorted(polygon_data.keys()):
        if pidx == 74:  # hidden polygon
            continue
        pdata = polygon_data[pidx]
        pts = pdata["points"]
        depth = pdata["depth"]
        if not pts:
            continue

        # Get current fillScale from the last appended line for this polygon
        # We stored it; reconstruct from the userData line
        xs_svg = [p[0] for p in pts]
        ys_svg = [p[1] for p in pts]
        bbox_w = max(xs_svg) - min(xs_svg)
        bbox_h = max(ys_svg) - min(ys_svg)
        if bbox_w <= 0 or bbox_h <= 0:
            continue
        fill_s = min(MAP_WIDTH / bbox_w, MAP_HEIGHT / bbox_h) * FILL_MARGIN
        fill_s = min(fill_s, MAX_FILL_SCALE)

        # Centroid in 3D
        cx = sum(xs_svg) / len(xs_svg)
        cy = sum(ys_svg) / len(ys_svg)
        cx_3d = cx
        cz_3d = -cy

        # Half extents of expanded polygon in 3D
        half_w = (bbox_w * fill_s) / 2.0
        half_h = (bbox_h * fill_s) / 2.0
        target_y = 0.75
        thickness = depth * 1.05  # 5% extrusion

        # 8 corners of expanded bounding box
        corners = []
        for dy in [target_y, target_y + thickness]:
            for dx in [-half_w, half_w]:
                for dz in [-half_h, half_h]:
                    corners.append((cx_3d + dx, dy, cz_3d + dz))

        # Check all corners fit within NDC_LIMIT
        max_ndc = 0.0
        for corner in corners:
            nx, ny = _project_point(vp, *corner)
            max_ndc = max(max_ndc, abs(nx), abs(ny))

        if max_ndc > NDC_LIMIT:
            # Reduce fillScale proportionally
            original_fill_s = fill_s
            # Binary search for the largest fillScale that fits
            lo, hi = 1.0, fill_s
            for _ in range(20):
                mid = (lo + hi) / 2.0
                hw = (bbox_w * mid) / 2.0
                hh = (bbox_h * mid) / 2.0
                worst = 0.0
                for dy in [target_y, target_y + thickness]:
                    for ddx in [-hw, hw]:
                        for ddz in [-hh, hh]:
                            nx, ny = _project_point(vp, cx_3d + ddx, dy, cz_3d + ddz)
                            worst = max(worst, abs(nx), abs(ny))
                if worst <= NDC_LIMIT:
                    lo = mid
                else:
                    hi = mid
            new_fill_s = round(lo, 2)
            # Update the line we already appended
            old_line = f"obj_c{pidx:03d}.userData.fillScale = {round(original_fill_s, 2)};"
            new_line = f"obj_c{pidx:03d}.userData.fillScale = {new_fill_s};"
            for i, line in enumerate(lines):
                if line == old_line:
                    lines[i] = new_line
                    break
            adjusted_count += 1
            name = polygon_to_name.get(pidx, f"c{pidx:03d}")
            print(f"    Frustum adjusted: {name} fillScale {round(original_fill_s, 2)} -> {new_fill_s}")

    ok_count = len([idx for idx in polygon_data.keys() if idx != 74]) - adjusted_count
    print(f"  Frustum check: {ok_count}/{ok_count + adjusted_count} polygons OK, {adjusted_count} adjusted")

    # Polygon array (exclude hidden c074)
    visible_polys = sorted(idx for idx in polygon_data.keys() if idx != 74)
    poly_items = [f"obj_c{idx:03d}" for idx in visible_polys]
    lines.append("")
    lines.append(f"const polygons = [{', '.join(poly_items)}];")
    lines.append("")

    userdata_block = "\n".join(lines)

    # Insert before raycaster section
    content = content.replace(
        "// Raycaster interaction",
        userdata_block + "\n// Raycaster interaction",
    )

    # 3. Add selectedPolygon state + animatePolygon function (UFO platform + camera)
    poly_state = (
        "\nlet selectedPolygon = null;\n"
        "let polyAnimTarget = null;\n"
        "let polyCenterWeight = 0;\n"
        "let cameraAnimTarget = null;\n"
        "\n"
        "// Camera rest position (cenital/drone)\n"
        "const CAM_REST_POS = new THREE.Vector3(0, 12, -0.001);\n"
        "const CAM_REST_TARGET = new THREE.Vector3(0, 0, 0);\n"
        "// Camera isometric position\n"
        "const CAM_ISO_POS = new THREE.Vector3(6, 6, -6);\n"
        "const CAM_ISO_TARGET = new THREE.Vector3(0, 0.75, 0);\n"
        "\n"
        "function resetBuildings(poly) {\n"
        "    if (poly && poly.userData.buildings) {\n"
        "        poly.userData.buildings.forEach(b => {\n"
        "            b.mesh.visible = false;\n"
        "            b.mesh.rotation.x = b.flatRotX;\n"
        "        });\n"
        "    }\n"
        "}\n"
        "\n"
        "function animatePolygon(poly) {\n"
        "    const now = performance.now();\n"
        "    if (selectedPolygon === poly) {\n"
        "        // Collapse: animate back to rest\n"
        "        polyAnimTarget = { poly: poly, targetY: 0, targetScale: 1.0,\n"
        "                           targetCenterW: 0, expanding: false,\n"
        "                           startY: poly.position.y, startS: poly.scale.x,\n"
        "                           startW: polyCenterWeight,\n"
        "                           targetThickness: 1, startThickness: poly.scale.y,\n"
        "                           startTime: now };\n"
        "        // Camera back to cenital\n"
        "        cameraAnimTarget = { startPos: camera.position.clone(),\n"
        "                             endPos: CAM_REST_POS.clone(),\n"
        "                             startTarget: controls.target.clone(),\n"
        "                             endTarget: CAM_REST_TARGET.clone(),\n"
        "                             startTime: now, duration: 500, expanding: false };\n"
        "        controls.enabled = false;\n"
        "        selectedPolygon = null;\n"
        "    } else {\n"
        "        // Snap-reset previous selection\n"
        "        if (selectedPolygon) {\n"
        "            resetBuildings(selectedPolygon);\n"
        "            selectedPolygon.position.set(0, 0, 0);\n"
        "            selectedPolygon.scale.set(1, 1, 1);\n"
        "            selectedPolygon.renderOrder = 0;\n"
        "            selectedPolygon.material.color.setHex(selectedPolygon.userData.originalColor);\n"
        "        }\n"
        "        polyCenterWeight = 0;\n"
        "        selectedPolygon = poly;\n"
        "        poly.renderOrder = 10;\n"
        "        // Save original color and set platform color\n"
        "        poly.userData.originalColor = poly.material.color.getHex();\n"
        "        poly.material.color.setHex(0xb4cfcb);\n"
        "        // Hide info card and deselect marker\n"
        "        card.style.display = 'none';\n"
        "        selectedMarker = null;\n"
        "        polyAnimTarget = { poly: poly, targetY: 0.75,\n"
        "                           targetScale: poly.userData.fillScale,\n"
        "                           targetCenterW: 1, expanding: true,\n"
        "                           startY: 0, startS: 1, startW: 0,\n"
        "                           targetThickness: 1.05, startThickness: 1,\n"
        "                           startTime: now };\n"
        "        // Camera to isometric\n"
        "        cameraAnimTarget = { startPos: camera.position.clone(),\n"
        "                             endPos: CAM_ISO_POS.clone(),\n"
        "                             startTarget: controls.target.clone(),\n"
        "                             endTarget: CAM_ISO_TARGET.clone(),\n"
        "                             startTime: now, duration: 800, expanding: true };\n"
        "        controls.enabled = false;\n"
        "    }\n"
        "}\n"
    )
    content = content.replace(
        "let selectedMarker = null;\n",
        "let selectedMarker = null;\n" + poly_state,
    )

    # 4. Modify click handler: UFO-aware (collapse on any click when expanded)
    old_click_end = (
        "        selectedMarker = hits[0].object;\n"
        "    } else {\n"
        "        card.style.display = 'none';\n"
        "        selectedMarker = null;\n"
        "    }\n"
        "});"
    )
    new_click_end = (
        "        selectedMarker = hits[0].object;\n"
        "        return;\n"
        "    }\n"
        "    // If polygon is expanded, collapse only on click INSIDE it\n"
        "    if (selectedPolygon) {\n"
        "        const polyHits = raycaster.intersectObjects([selectedPolygon]);\n"
        "        if (polyHits.length > 0) {\n"
        "            animatePolygon(selectedPolygon);\n"
        "        }\n"
        "        return;\n"
        "    }\n"
        "    const polyHits = raycaster.intersectObjects(polygons);\n"
        "    if (polyHits.length > 0) {\n"
        "        animatePolygon(polyHits[0].object);\n"
        "    } else {\n"
        "        card.style.display = 'none';\n"
        "        selectedMarker = null;\n"
        "    }\n"
        "});"
    )
    content = content.replace(old_click_end, new_click_end)

    # 5. Modify mousemove handler: pointer when expanded (click-to-close hint)
    old_move_end = (
        "    const hits = raycaster.intersectObjects(markers);\n"
        "    renderer.domElement.style.cursor = hits.length > 0 ? 'pointer' : 'default';\n"
        "});"
    )
    new_move_end = (
        "    // When polygon is expanded, pointer only over the platform\n"
        "    if (selectedPolygon) {\n"
        "        const polyHover = raycaster.intersectObjects([selectedPolygon]);\n"
        "        renderer.domElement.style.cursor = polyHover.length > 0 ? 'pointer' : 'default';\n"
        "        return;\n"
        "    }\n"
        "    const markerHits = raycaster.intersectObjects(markers);\n"
        "    if (markerHits.length > 0) {\n"
        "        renderer.domElement.style.cursor = 'pointer';\n"
        "        return;\n"
        "    }\n"
        "    const polyHits = raycaster.intersectObjects(polygons);\n"
        "    renderer.domElement.style.cursor = polyHits.length > 0 ? 'pointer' : 'default';\n"
        "});"
    )
    content = content.replace(old_move_end, new_move_end)

    # 6. Add UFO platform + camera + building rotation animation in animate loop
    old_animate = (
        "    controls.update();\n"
        "    renderer.render(scene, camera);"
    )
    new_animate = (
        "    // UFO platform animation (time-based with ease-out)\n"
        "    if (polyAnimTarget) {\n"
        "        const p = polyAnimTarget.poly;\n"
        "        const cX = p.userData.centroidX;\n"
        "        const cZ = p.userData.centroidZ;\n"
        "        const tY = polyAnimTarget.targetY;\n"
        "        const tS = polyAnimTarget.targetScale;\n"
        "        const tW = polyAnimTarget.targetCenterW;\n"
        "        const tTh = polyAnimTarget.targetThickness;\n"
        "        const elapsed = performance.now() - polyAnimTarget.startTime;\n"
        "        const duration = polyAnimTarget.expanding ? 800 : 500;\n"
        "        const t = Math.min(elapsed / duration, 1);\n"
        "        const e = 1 - Math.pow(1 - t, 3);  // ease-out cubic\n"
        "        // Interpolate from start to target\n"
        "        const newS = polyAnimTarget.startS + (tS - polyAnimTarget.startS) * e;\n"
        "        const newTh = polyAnimTarget.startThickness + (tTh - polyAnimTarget.startThickness) * e;\n"
        "        p.scale.set(newS, newTh, newS);\n"
        "        polyCenterWeight = polyAnimTarget.startW + (tW - polyAnimTarget.startW) * e;\n"
        "        p.position.x = cX * (1 - newS - polyCenterWeight);\n"
        "        p.position.z = cZ * (1 - newS - polyCenterWeight);\n"
        "        p.position.y = polyAnimTarget.startY + (tY - polyAnimTarget.startY) * e;\n"
        "        // Position buildings on platform + animate rotation (flat -> standing)\n"
        "        if (p.userData.buildings) {\n"
        "            const worldCX = p.position.x + cX * newS;\n"
        "            const worldCZ = p.position.z + cZ * newS;\n"
        "            p.userData.buildings.forEach(b => {\n"
        "                b.mesh.position.x = worldCX + b.offsetX * newS;\n"
        "                b.mesh.position.z = worldCZ + b.offsetZ * newS;\n"
        "                b.mesh.position.y = p.position.y + p.userData.depth * p.scale.y + 0.005;\n"
        "                b.mesh.scale.setScalar(newS);\n"
        "                // Animate rotation: flat (flatRotX) -> standing (0)\n"
        "                if (polyAnimTarget.expanding) {\n"
        "                    b.mesh.visible = true;\n"
        "                    b.mesh.rotation.x = b.flatRotX * (1 - e);\n"
        "                    // Offset Y when standing so base sits on platform\n"
        "                    b.mesh.position.y += b.heightOffset * newS * e;\n"
        "                } else {\n"
        "                    b.mesh.rotation.x = b.flatRotX * e;\n"
        "                    b.mesh.position.y += b.heightOffset * newS * (1 - e);\n"
        "                }\n"
        "            });\n"
        "        }\n"
        "        // Done?\n"
        "        if (t >= 1) {\n"
        "            if (polyAnimTarget.expanding) {\n"
        "                p.scale.set(tS, tTh, tS);\n"
        "                polyCenterWeight = tW;\n"
        "                p.position.x = cX * (1 - tS - tW);\n"
        "                p.position.z = cZ * (1 - tS - tW);\n"
        "                p.position.y = tY;\n"
        "                // Snap buildings to standing\n"
        "                if (p.userData.buildings) {\n"
        "                    p.userData.buildings.forEach(b => { b.mesh.rotation.x = 0; });\n"
        "                }\n"
        "                polyAnimTarget = null;\n"
        "            } else {\n"
        "                resetBuildings(p);\n"
        "                p.position.set(0, 0, 0);\n"
        "                p.scale.set(1, 1, 1);\n"
        "                p.renderOrder = 0;\n"
        "                p.material.color.setHex(p.userData.originalColor);\n"
        "                polyCenterWeight = 0;\n"
        "                polyAnimTarget = null;\n"
        "            }\n"
        "        }\n"
        "    }\n"
        "    // Camera animation (cenital <-> isometric)\n"
        "    if (cameraAnimTarget) {\n"
        "        const elapsed = performance.now() - cameraAnimTarget.startTime;\n"
        "        const t = Math.min(elapsed / cameraAnimTarget.duration, 1);\n"
        "        const e = 1 - Math.pow(1 - t, 3);  // ease-out cubic\n"
        "        camera.position.lerpVectors(cameraAnimTarget.startPos, cameraAnimTarget.endPos, e);\n"
        "        controls.target.lerpVectors(cameraAnimTarget.startTarget, cameraAnimTarget.endTarget, e);\n"
        "        if (t >= 1) {\n"
        "            camera.position.copy(cameraAnimTarget.endPos);\n"
        "            controls.target.copy(cameraAnimTarget.endTarget);\n"
        "            controls.enabled = true;\n"
        "            controls.enableRotate = cameraAnimTarget.expanding;\n"
        "            cameraAnimTarget = null;\n"
        "        }\n"
        "    }\n"
        "    controls.update();\n"
        "    renderer.render(scene, camera);"
    )
    content = content.replace(old_animate, new_animate)

    return content


# ---------------------------------------------------------------------------
# 3D Buildings on platforms
# ---------------------------------------------------------------------------
# Buildings live in app/static/js/<subfolder>/*.json
# common/   → scope:all (injected into main file)
# gijon/    → c013 specific (generated into gijon/index.js)
# oviedo/   → c005 specific (generated into oviedo/index.js)
# The legacy scripts/buildings/ is kept as a fallback if the new structure is absent.
STATIC_JS_DIR   = PROJECT_ROOT / "app" / "static" / "js"
BUILDINGS_DIR   = PROJECT_ROOT / "scripts" / "buildings"  # legacy fallback


def _load_subdir_configs(subdir):
    """Load JSON configs from a single subdirectory."""
    configs = []
    for f in sorted(subdir.glob("*.json")):
        data = json.loads(f.read_text(encoding="utf-8"))
        data["_source_dir"] = subdir.name  # track origin folder
        configs.append(data)
    return configs


def load_building_configs():
    """Load all building JSON files (all subdirs of app/static/js/).

    Returns all configs (scope:all + municipality-specific).
    Falls back to scripts/buildings/ if no subdirs with JSONs found.
    """
    configs = []
    subdirs = [d for d in STATIC_JS_DIR.iterdir() if d.is_dir()]
    for subdir in sorted(subdirs):
        configs.extend(_load_subdir_configs(subdir))
    if configs:
        return configs

    # Fallback: legacy scripts/buildings/
    if BUILDINGS_DIR.exists():
        for f in sorted(BUILDINGS_DIR.glob("*.json")):
            data = json.loads(f.read_text(encoding="utf-8"))
            configs.append(data)
    return configs


def generate_municipality_modules():
    """Generate app/static/js/{slug}/index.js for each municipality subfolder.

    Reads *.json files from non-common subdirectories and emits an ES module
    exporting load(scene, polygon) and optionally update(t).
    Skips 'common/' (scope:all items handled by inject_buildings).
    """
    subdirs = [d for d in STATIC_JS_DIR.iterdir()
               if d.is_dir() and d.name != "common"]
    for subdir in sorted(subdirs):
        configs = _load_subdir_configs(subdir)
        muni_cfgs = [c for c in configs
                     if c.get("scope") != "all" and c.get("enabled", True)]
        if not muni_cfgs:
            continue
        _write_municipality_index(subdir, muni_cfgs)


def _write_municipality_index(subdir, configs):
    """Write {subdir}/index.js from a list of building configs."""
    slug = subdir.name
    lines = []
    imports = [
        "import * as THREE from '/static/vendor/three/three.module.js';",
    ]

    needs_gltf = any(c.get("type") == "glb" for c in configs)
    if needs_gltf:
        imports.append(
            "import { GLTFLoader } from '/static/vendor/three/GLTFLoader.js';"
        )
    for cfg in configs:
        if cfg.get("type") == "module_import":
            src = cfg["src"]
            export_name = cfg["exportName"]
            imports.append(f"import {{ {export_name} }} from '{src}';")

    lines.extend(imports)
    lines.append("")

    # Module-level animation part variables and module_import result vars
    anim_entries = []   # list of (var_name, cfg) with animations
    mod_entries  = []   # list of (result_var, cfg) for module_import
    for cfg in configs:
        vn = _sanitize_varname(cfg["name"])
        if cfg.get("type") == "composite" and cfg.get("animations"):
            for a in cfg["animations"]:
                pi = a["partIndex"]
                lines.append(f"let _{vn}_p{pi} = null;")
            anim_entries.append((vn, cfg))
        if cfg.get("type") == "module_import":
            rv = f"_mod_{vn}"
            lines.append(f"let {rv} = null;")
            mod_entries.append((rv, cfg))
    if anim_entries or mod_entries:
        lines.append("")

    # export async function load(scene, polygon)
    lines.append("export async function load(scene, polygon) {")
    lines.append("    if (!polygon.userData.buildings) polygon.userData.buildings = [];")
    lines.append("")

    for cfg in configs:
        name = cfg["name"]
        btype = cfg.get("type", "extrude")
        vn = _sanitize_varname(name)
        ox = cfg.get("offsetX", 0.0)
        oz = cfg.get("offsetZ", 0.0)
        ho = cfg.get("heightOffset", 0.0)
        rx = cfg.get("rotateX", "-Math.PI / 2")
        ry = cfg.get("rotateY")

        lines.append(f"    // ── {name} ──")

        if btype == "composite":
            parts = cfg["parts"]
            color = cfg.get("color", "0xcccccc")
            lines.append(f"    const {vn}_mat = new THREE.MeshLambertMaterial({{ color: {color}, side: THREE.DoubleSide }});")
            lines.append(f"    const {vn}_group = new THREE.Group();")
            max_y = 0.0
            for pi, part in enumerate(parts):
                geo_type = part["geometry"]
                params = part["params"]
                pvar = f"{vn}_p{pi}"
                if geo_type == "box":
                    w, h, d = params["width"], params["height"], params["depth"]
                    lines.append(f"    const {pvar}_geo = new THREE.BoxGeometry({w}, {h}, {d});")
                elif geo_type == "cylinder":
                    rt = params.get("radiusTop", params.get("radius", 0.01))
                    rb = params.get("radiusBottom", params.get("radius", 0.01))
                    h = params["height"]
                    rs = params.get("radialSegments", 8)
                    lines.append(f"    const {pvar}_geo = new THREE.CylinderGeometry({rt}, {rb}, {h}, {rs});")
                elif geo_type == "cone":
                    lines.append(f"    const {pvar}_geo = new THREE.ConeGeometry({params['radius']}, {params['height']}, {params.get('radialSegments',6)});")
                elif geo_type == "torus":
                    arc = params.get("arc", "Math.PI * 2")
                    lines.append(f"    const {pvar}_geo = new THREE.TorusGeometry({params['radius']}, {params['tube']}, {params.get('radialSegments',8)}, {params.get('tubularSegments',16)}, {arc});")
                else:
                    continue
                pc = part.get("color")
                po = part.get("opacity")
                if pc or po is not None:
                    c2 = pc or color
                    if po is not None:
                        lines.append(f"    const {pvar}_mat = new THREE.MeshLambertMaterial({{ color: {c2}, side: THREE.DoubleSide, transparent: true, opacity: {po} }});")
                    else:
                        lines.append(f"    const {pvar}_mat = new THREE.MeshLambertMaterial({{ color: {c2}, side: THREE.DoubleSide }});")
                    mat_ref = f"{pvar}_mat"
                else:
                    mat_ref = f"{vn}_mat"
                lines.append(f"    const {pvar} = new THREE.Mesh({pvar}_geo, {mat_ref});")
                pos = part.get("position")
                if pos:
                    lines.append(f"    {pvar}.position.set({pos[0]}, {pos[1]}, {pos[2]});")
                    part_top = pos[1]
                    if geo_type in ("box", "cylinder", "cone"):
                        part_top += params["height"] / 2
                    elif geo_type == "torus":
                        part_top += params["radius"] + params["tube"]
                    max_y = max(max_y, part_top)
                rot = part.get("rotation")
                if rot:
                    for axis in ("x", "y", "z"):
                        v = rot.get(axis)
                        if v is not None:
                            lines.append(f"    {pvar}.rotation.{axis} = {v};")
                lines.append(f"    {vn}_group.add({pvar});")
                # Assign animated parts to module-level vars
                if cfg.get("animations"):
                    for a in cfg["animations"]:
                        if a["partIndex"] == pi:
                            lines.append(f"    _{vn}_p{pi} = {pvar};")
            if "heightOffset" in cfg:
                ho = cfg["heightOffset"]
            else:
                ho = round(max_y / 2, 4)
            lines.append(f"    {vn}_group.rotation.x = {rx};")
            if ry:
                lines.append(f"    {vn}_group.rotation.y = {ry};")
            lines.append(f"    {vn}_group.visible = false;")
            lines.append(f"    {vn}_group.renderOrder = 11;")
            lines.append(f"    scene.add({vn}_group);")
            lines.append(f"    polygon.userData.buildings.push({{ mesh: {vn}_group, offsetX: {ox}, offsetZ: {oz}, flatRotX: {rx}, heightOffset: {ho} }});")

        elif btype == "glb":
            src = cfg["src"]
            ns = cfg.get("normalizedScale", 0.1)
            rot = cfg.get("rotation", {})
            rot_x = rot.get("x", -1.5708)
            rot_y = rot.get("y", 0)
            lines.append(f"    new GLTFLoader().load('{src}', (gltf) => {{")
            lines.append(f"        const _inner = gltf.scene;")
            lines.append(f"        const _box = new THREE.Box3().setFromObject(_inner);")
            lines.append(f"        const _sz = new THREE.Vector3(); _box.getSize(_sz);")
            lines.append(f"        const _s = {ns} / Math.max(_sz.x, _sz.y, _sz.z);")
            lines.append(f"        _inner.scale.setScalar(_s);")
            lines.append(f"        _inner.position.y = -_box.min.y * _s;")
            lines.append(f"        const _w = new THREE.Group(); _w.add(_inner);")
            lines.append(f"        _w.rotation.x = {rot_x}; _w.rotation.y = {rot_y};")
            lines.append(f"        _w.visible = false; scene.add(_w);")
            lines.append(f"        polygon.userData.buildings.push({{ mesh: _w, offsetX: {ox}, offsetZ: {oz}, flatRotX: {rot_x}, heightOffset: {ho} }});")
            lines.append(f"        // Show immediately if polygon already expanded")
            lines.append(f"        if (_w.parent && polygon.position.y > 0) _w.visible = true;")
            lines.append(f"    }});")

        elif btype == "module_import":
            export_name = cfg["exportName"]
            rv = f"_mod_{vn}"
            frx = cfg.get("flatRotX", -1.5708)
            lines.append(f"    try {{")
            lines.append(f"        const _r = await {export_name}(scene);")
            lines.append(f"        {rv} = _r;")
            lines.append(f"        _r.group.renderOrder = 11;")
            lines.append(f"        polygon.userData.buildings.push({{ mesh: _r.group, offsetX: {ox}, offsetZ: {oz}, flatRotX: {frx}, heightOffset: {ho} }});")
            lines.append(f"    }} catch(e) {{ console.error('{name}:', e); }}")

        lines.append("")

    lines.append("}")
    lines.append("")

    # export function update(t) — only if there are animations or hasUpdate modules
    needs_update = anim_entries or any(c.get("hasUpdate") for _, c in mod_entries)
    if needs_update:
        lines.append("export function update(t) {")
        for vn, cfg in anim_entries:
            first_pi = cfg["animations"][0]["partIndex"]
            lines.append(f"    if (_{vn}_p{first_pi}) {{")
            for a in cfg["animations"]:
                pi = a["partIndex"]
                pvar = f"_{vn}_p{pi}"
                sx, sy = a["speedX"], a["speedY"]
                ax2, ay2 = a["amplitudeX"], a["amplitudeY"]
                cx, cy = a["centerX"], a["centerY"]
                ph = a.get("phase", 0)
                lines.append(f"        {pvar}.position.x = {cx} + Math.sin(t * {sx} + {ph}) * {ax2};")
                lines.append(f"        {pvar}.position.y = {cy} + Math.sin(t * {sy} + {ph}) * {ay2};")
            lines.append("    }")
        for rv, cfg in mod_entries:
            if cfg.get("hasUpdate"):
                lines.append(f"    {rv}?.update?.(t);")
        lines.append("}")
        lines.append("")

    out_path = subdir / "index.js"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"  Generated {out_path.relative_to(PROJECT_ROOT)} ({len(configs)} buildings)")


def _sanitize_varname(name):
    """Convert a building name to a valid JS variable name fragment."""
    return (
        name.lower()
        .replace(" ", "_")
        .replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u")
        .replace("ñ", "n")
    )


def _build_composite_parts(lines, var_name, cfg):
    """Emit JS for composite sub-meshes. Returns (height_offset, anim_lines)."""
    parts = cfg["parts"]
    color = cfg.get("color", "0xcccccc")
    lines.append(f"const {var_name}_mat = new THREE.MeshLambertMaterial({{ "
                 f"color: {color}, side: THREE.DoubleSide }});")
    lines.append(f"const {var_name}_group = new THREE.Group();")
    max_y_extent = 0.0
    for pi, part in enumerate(parts):
        geo_type = part["geometry"]
        params = part["params"]
        pvar = f"{var_name}_p{pi}"
        if geo_type == "torus":
            radius = params["radius"]
            tube = params["tube"]
            radial = params.get("radialSegments", 8)
            tubular = params.get("tubularSegments", 16)
            arc_expr = params.get("arc", "Math.PI * 2")
            lines.append(f"const {pvar}_geo = new THREE.TorusGeometry("
                         f"{radius}, {tube}, {radial}, {tubular}, {arc_expr});")
        elif geo_type == "box":
            w, h, d = params["width"], params["height"], params["depth"]
            lines.append(f"const {pvar}_geo = new THREE.BoxGeometry({w}, {h}, {d});")
        elif geo_type == "cylinder":
            r_top = params.get("radiusTop", params.get("radius", 0.01))
            r_bot = params.get("radiusBottom", params.get("radius", 0.01))
            h = params["height"]
            radial = params.get("radialSegments", 8)
            lines.append(f"const {pvar}_geo = new THREE.CylinderGeometry("
                         f"{r_top}, {r_bot}, {h}, {radial});")
        elif geo_type == "cone":
            radius = params["radius"]
            h = params["height"]
            radial = params.get("radialSegments", 6)
            lines.append(f"const {pvar}_geo = new THREE.ConeGeometry({radius}, {h}, {radial});")
        else:
            print(f"    WARNING: Unknown geometry type '{geo_type}' in composite part {pi}")
            continue
        part_color = part.get("color")
        part_opacity = part.get("opacity")
        if part_color or part_opacity is not None:
            pc = part_color or color
            if part_opacity is not None:
                lines.append(f"const {pvar}_mat = new THREE.MeshLambertMaterial({{ "
                             f"color: {pc}, side: THREE.DoubleSide, "
                             f"transparent: true, opacity: {part_opacity} }});")
            else:
                lines.append(f"const {pvar}_mat = new THREE.MeshLambertMaterial({{ "
                             f"color: {pc}, side: THREE.DoubleSide }});")
            mat_ref = f"{pvar}_mat"
        else:
            mat_ref = f"{var_name}_mat"
        lines.append(f"const {pvar} = new THREE.Mesh({pvar}_geo, {mat_ref});")
        pos = part.get("position")
        if pos:
            lines.append(f"{pvar}.position.set({pos[0]}, {pos[1]}, {pos[2]});")
        rot = part.get("rotation")
        if rot:
            if rot.get("order"):
                lines.append(f"{pvar}.rotation.order = '{rot['order']}';")
            for axis in ("x", "y", "z"):
                val = rot.get(axis)
                if val is not None:
                    lines.append(f"{pvar}.rotation.{axis} = {val};")
        lines.append(f"{var_name}_group.add({pvar});")
        if pos:
            part_top = pos[1]
            if geo_type == "torus":
                part_top += params["radius"] + params["tube"]
            elif geo_type in ("box", "cylinder", "cone"):
                part_top += params["height"] / 2
            max_y_extent = max(max_y_extent, part_top)

    height_offset = round(max_y_extent / 2, 4)
    if "heightOffset" in cfg:
        height_offset = cfg["heightOffset"]

    # Build animation lines
    anim_lines = []
    animations = cfg.get("animations", [])
    if animations:
        name_label = cfg.get("name", var_name)
        anim_lines.append(f"    // --- {name_label} animation ---")
        anim_lines.append(f"    if ({var_name}_group.visible) {{")
        for a in animations:
            pi = a["partIndex"]
            pvar = f"{var_name}_p{pi}"
            sx, sy = a["speedX"], a["speedY"]
            ax, ay = a["amplitudeX"], a["amplitudeY"]
            cx, cy = a["centerX"], a["centerY"]
            ph = a.get("phase", 0)
            anim_lines.append(f"        {pvar}.position.x = {cx} + Math.sin(_t * {sx} + {ph}) * {ax};")
            anim_lines.append(f"        {pvar}.position.y = {cy} + Math.sin(_t * {sy} + {ph}) * {ay};")
            if a.get("rotate", True):
                anim_lines.append(f"        {pvar}.rotation.z = Math.cos(_t * {sx} + {ph}) > 0 ? Math.PI/2 : -Math.PI/2;")
        anim_lines.append("    }")

    return height_offset, anim_lines


def inject_buildings(content):
    """Inject 3D building meshes that appear on polygon platforms.

    Supports geometry types:
    - "composite": Group of sub-meshes (torus, box, cylinder, cone) for complex shapes
    - "extrudePath": ExtrudeGeometry with extrudePath (arcs)
    - "glb": GLTF/GLB model loaded via GLTFLoader
    - "module_import": ES module with an async factory function
    - "scope:all" composite: factory function + polygons.forEach (all municipalities)
    - default: ExtrudeGeometry from 2D silhouette (footprints)
    """
    configs = load_building_configs()
    if not configs:
        print("  No building configs found")
        return content

    lines = [
        "",
        "// --- 3D Buildings on platforms ---",
    ]
    all_anim_lines = []  # animation code to inject in animate()
    module_import_lines = []  # ES import lines for MODULE_IMPORTS_INJECT_POINT
    animate_cb_lines = []  # per-frame callbacks for ANIMATE_CALLBACKS_INJECT_POINT
    needs_gltf_loader = False

    # ── Separate scope:all from municipality-specific ────────────────────────
    all_cfgs = [c for c in configs if c.get("scope") == "all" and c.get("enabled", True)]
    muni_cfgs = [c for c in configs if c.get("scope") != "all" and c.get("enabled", True)]

    # ── scope:all — factory function + polygons.forEach ──────────────────────
    for cfg in all_cfgs:
        name = cfg["name"]
        building_type = cfg.get("type", "composite")
        if building_type != "composite":
            print(f"  WARNING: scope:all only supports composite type (skipping {name})")
            continue
        var_name = _sanitize_varname(name)
        tipo = cfg.get("tipo", var_name)
        offset_x = cfg.get("offsetX", 0.0)
        offset_z = cfg.get("offsetZ", 0.0)

        # Emit factory function that builds ONE copy of the composite
        factory_lines = []
        factory_lines.append(f"function _make_{var_name}() {{")
        sub = []
        height_offset, anim_lines = _build_composite_parts(sub, f"_f_{var_name}", cfg)
        # Rename group inside factory to _g
        sub_js = "\n".join(sub)
        sub_js = sub_js.replace(f"const _f_{var_name}_group", "const _g")
        sub_js = sub_js.replace(f"_f_{var_name}_group", "_g")
        sub_js = sub_js.replace(f"const _f_{var_name}_mat", f"const _f_{var_name}_mat")
        # Prefix each line with 4 spaces for function body
        for l in sub_js.splitlines():
            factory_lines.append("    " + l)
        # Set tipo, clickable, visibility on the group
        rotate_x = cfg.get("rotateX", "-Math.PI / 2")
        rotate_y = cfg.get("rotateY")
        factory_lines.append(f"    _g.rotation.x = {rotate_x};")
        if rotate_y:
            factory_lines.append(f"    _g.rotation.y = {rotate_y};")
        factory_lines.append(f"    _g.userData.tipo = '{tipo}';")
        factory_lines.append(f"    _g.userData.clickable = true;")
        factory_lines.append(f"    _g.visible = false;")
        factory_lines.append(f"    _g.renderOrder = 11;")
        factory_lines.append(f"    return _g;")
        factory_lines.append(f"}}")

        lines.extend(factory_lines)
        lines.append(f"polygons.forEach(p => {{")
        lines.append(f"    const _mesh = _make_{var_name}();")
        lines.append(f"    scene.add(_mesh);")
        lines.append(f"    if (!p.userData.buildings) p.userData.buildings = [];")
        lines.append(f"    p.userData.buildings.push({{")
        lines.append(f"        mesh: _mesh, offsetX: {offset_x}, offsetZ: {offset_z},")
        lines.append(f"        flatRotX: {rotate_x}, heightOffset: {height_offset}")
        lines.append(f"    }});")
        lines.append(f"}});")
        lines.append("")
        print(f"  Added scope:all building: {name} (tipo={tipo})")

    # ── municipality-specific → handled by generate_municipality_modules() ────
    if muni_cfgs:
        print(f"  (Skipping {len(muni_cfgs)} municipality-specific items → generated in index.js modules)")

    # NOTE: the code below handles legacy extrude/extrudePath types that may
    # appear in the fallback scripts/buildings/ folder. It is only reached
    # if muni_cfgs contains items not covered by the new architecture.
    for cfg in []:  # disabled — municipality items go to index.js
        name = cfg["name"]
        building_type = cfg.get("type", "extrude")

        var_name = _sanitize_varname(name)
        poly_id = cfg.get("concejoPolygon", "c000")
        poly_var = f"obj_{poly_id}"
        offset_x = cfg.get("offsetX", 0.0)
        offset_z = cfg.get("offsetZ", 0.0)

        # ── GLB type ──────────────────────────────────────────────────────────
        if building_type == "glb":
            needs_gltf_loader = True
            src = cfg["src"]
            norm_scale = cfg.get("normalizedScale", 0.1)
            rot = cfg.get("rotation", {})
            rot_x = rot.get("x", -1.5708)
            rot_y = rot.get("y", 0)
            height_offset = cfg.get("heightOffset", 0.0)

            lines.append(f"// GLB: {name} on {poly_id}")
            lines.append(f"{{")
            lines.append(f"    const _loader_{var_name} = new GLTFLoader();")
            lines.append(f"    _loader_{var_name}.load('{src}', (gltf) => {{")
            lines.append(f"        const _inner = gltf.scene;")
            lines.append(f"        const _box = new THREE.Box3().setFromObject(_inner);")
            lines.append(f"        const _sz = new THREE.Vector3();")
            lines.append(f"        _box.getSize(_sz);")
            lines.append(f"        const _maxDim = Math.max(_sz.x, _sz.y, _sz.z);")
            lines.append(f"        const _innerScale = _maxDim > 0 ? {norm_scale} / _maxDim : 1;")
            lines.append(f"        _inner.scale.setScalar(_innerScale);")
            lines.append(f"        _inner.position.y = -_box.min.y * _innerScale;")
            lines.append(f"        const _wrapper_{var_name} = new THREE.Group();")
            lines.append(f"        _wrapper_{var_name}.add(_inner);")
            lines.append(f"        _wrapper_{var_name}.rotation.x = {rot_x};")
            lines.append(f"        _wrapper_{var_name}.rotation.y = {rot_y};")
            lines.append(f"        _wrapper_{var_name}.visible = false;")
            lines.append(f"        scene.add(_wrapper_{var_name});")
            lines.append(f"        if (!{poly_var}.userData.buildings) {poly_var}.userData.buildings = [];")
            lines.append(f"        {poly_var}.userData.buildings.push({{")
            lines.append(f"            mesh: _wrapper_{var_name}, offsetX: {offset_x}, offsetZ: {offset_z},")
            lines.append(f"            flatRotX: {rot_x}, heightOffset: {height_offset}")
            lines.append(f"        }});")
            lines.append(f"        console.log('{name} vinculado a la plataforma {poly_id}');")
            lines.append(f"    }});")
            lines.append(f"}}")
            lines.append("")
            print(f"  Added GLB building: {name} -> {poly_id}")
            continue

        # ── module_import type ────────────────────────────────────────────────
        if building_type == "module_import":
            src = cfg["src"]
            export_name = cfg["exportName"]
            offset_x = cfg.get("offsetX", 0.0)
            offset_z = cfg.get("offsetZ", 0.0)
            height_offset = cfg.get("heightOffset", 0.0)
            has_update = cfg.get("hasUpdate", False)

            # Variable name for the module result
            result_var = f"_mod_{var_name}"

            # ES import + let declaration → MODULE_IMPORTS_INJECT_POINT
            module_import_lines.append(f"import {{ {export_name} }} from '{src}';")
            module_import_lines.append(f"let {result_var} = null;")

            # Async call + buildings registration → BUILDINGS_INJECT_POINT
            lines.append(f"// module_import: {name} on {poly_id}")
            lines.append(f"{export_name}(scene).then(result => {{")
            lines.append(f"    {result_var} = result;")
            lines.append(f"    result.group.renderOrder = 11;")
            lines.append(f"    if (!{poly_var}.userData.buildings) {poly_var}.userData.buildings = [];")
            lines.append(f"    {poly_var}.userData.buildings.push({{")
            lines.append(f"        mesh: result.group, offsetX: {offset_x}, offsetZ: {offset_z},")
            lines.append(f"        heightOffset: {height_offset}")
            lines.append(f"    }});")
            lines.append(f"    console.log('{name} vinculado a la plataforma {poly_id}');")
            lines.append(f"}}).catch(e => console.error('Error {name}:', e));")
            lines.append("")

            # Animate callback → ANIMATE_CALLBACKS_INJECT_POINT
            if has_update:
                animate_cb_lines.append(f"    if ({result_var}?.update) {result_var}.update(_t);")

            print(f"  Added module_import building: {name} -> {poly_id}")
            continue

        # ── composite type ────────────────────────────────────────────────────
        if building_type == "composite":
            color = cfg.get("color", "0xcccccc")
            sub = []
            height_offset, anim_lines = _build_composite_parts(sub, var_name, cfg)
            lines.extend(sub)

            rotate_x = cfg.get("rotateX", "-Math.PI / 2")
            rotate_y = cfg.get("rotateY")
            lines.append(f"{var_name}_group.rotation.x = {rotate_x};")
            if rotate_y:
                lines.append(f"{var_name}_group.rotation.y = {rotate_y};")
            lines.append(f"{var_name}_group.visible = false;")
            lines.append(f"{var_name}_group.renderOrder = 11;")
            lines.append(f"scene.add({var_name}_group);")
            lines.append(f"if (!{poly_var}.userData.buildings) {poly_var}.userData.buildings = [];")
            lines.append(
                f"{poly_var}.userData.buildings.push({{ mesh: {var_name}_group, "
                f"offsetX: {offset_x}, offsetZ: {offset_z}, "
                f"flatRotX: {rotate_x}, heightOffset: {height_offset} }});"
            )
            lines.append("")
            all_anim_lines.extend(anim_lines)
            if anim_lines:
                print(f"  Animations: {len(cfg.get('animations',[]))} swim animations for {name}")
            print(f"  Added composite building: {name} -> {poly_id}")
            continue

        # ── extrudePath type ──────────────────────────────────────────────────
        color = cfg.get("color", "0xcccccc")
        lines.append(
            f"const {var_name}_mat = new THREE.MeshLambertMaterial({{ "
            f"color: {color}, side: THREE.DoubleSide }});"
        )
        if building_type == "extrudePath":
            cross_pts = cfg["crossSection"]
            path_pts = cfg["path"]
            steps = cfg.get("steps", 12)
            first = cross_pts[0]
            lines.append(f"const {var_name}_shape = new THREE.Shape();")
            lines.append(f"{var_name}_shape.moveTo({first[0]}, {first[1]});")
            for pt in cross_pts[1:]:
                lines.append(f"{var_name}_shape.lineTo({pt[0]}, {pt[1]});")
            pts_str = ", ".join(
                f"new THREE.Vector3({p[0]}, {p[1]}, {p[2]})" for p in path_pts
            )
            lines.append(f"const {var_name}_path = new THREE.CatmullRomCurve3([{pts_str}]);")
            lines.append(
                f"const {var_name}_geo = new THREE.ExtrudeGeometry({var_name}_shape, "
                f"{{ extrudePath: {var_name}_path, steps: {steps}, bevelEnabled: false }});"
            )
            max_y = max(p[1] for p in path_pts)
            height_offset = round(max_y / 2, 4)
            if "heightOffset" in cfg:
                height_offset = cfg["heightOffset"]
            log_detail = f"extrudePath {len(path_pts)} path pts, {len(cross_pts)} cross pts, steps={steps}"
        else:
            # default: extrude from 2D footprint
            depth = cfg["extrudeDepth"]
            outer_points = cfg["outer"]
            hole_lists = cfg.get("holes", [])
            first = outer_points[0]
            lines.append(f"const {var_name}_shape = new THREE.Shape();")
            lines.append(f"{var_name}_shape.moveTo({first[0]}, {first[1]});")
            for pt in outer_points[1:]:
                lines.append(f"{var_name}_shape.lineTo({pt[0]}, {pt[1]});")
            for hi, hole_pts in enumerate(hole_lists):
                hole_var = f"{var_name}_hole{hi}"
                lines.append(f"const {hole_var} = new THREE.Path();")
                lines.append(f"{hole_var}.moveTo({hole_pts[0][0]}, {hole_pts[0][1]});")
                for pt in hole_pts[1:]:
                    lines.append(f"{hole_var}.lineTo({pt[0]}, {pt[1]});")
                lines.append(f"{var_name}_shape.holes.push({hole_var});")
            lines.append(
                f"const {var_name}_geo = new THREE.ExtrudeGeometry({var_name}_shape, "
                f"{{ depth: {depth}, bevelEnabled: false }});"
            )
            lines.append(f"{var_name}_geo.translate(0, 0, -{depth / 2});")
            all_ys = [pt[1] for pt in outer_points]
            shape_height = max(all_ys) - min(all_ys)
            height_offset = round(shape_height / 2, 4)
            if "heightOffset" in cfg:
                height_offset = cfg["heightOffset"]
            log_detail = f"{len(outer_points)} outer pts, {len(hole_lists)} holes, depth={depth}"

        rotate_x = cfg.get("rotateX", "-Math.PI / 2")
        rotate_y = cfg.get("rotateY")
        lines.append(f"const {var_name}_mesh = new THREE.Mesh({var_name}_geo, {var_name}_mat);")
        lines.append(f"{var_name}_mesh.rotation.x = {rotate_x};")
        if rotate_y:
            lines.append(f"{var_name}_mesh.rotation.y = {rotate_y};")
        lines.append(f"{var_name}_mesh.visible = false;")
        lines.append(f"{var_name}_mesh.renderOrder = 11;")
        lines.append(f"scene.add({var_name}_mesh);")
        lines.append(f"if (!{poly_var}.userData.buildings) {poly_var}.userData.buildings = [];")
        lines.append(
            f"{poly_var}.userData.buildings.push({{ mesh: {var_name}_mesh, "
            f"offsetX: {offset_x}, offsetZ: {offset_z}, "
            f"flatRotX: {rotate_x}, heightOffset: {height_offset} }});"
        )
        lines.append("")
        print(f"  Added building: {name} -> {poly_id} ({log_detail})")

    building_block = "\n".join(lines)

    # ── Inject building block at BUILDINGS_INJECT_POINT ──────────────────────
    inject_marker = "// ===== BUILDINGS_INJECT_POINT ====="
    if inject_marker in content:
        content = content.replace(inject_marker, building_block)
    else:
        # Legacy fallback: inject before "// Animation with pulse\n"
        content = content.replace(
            "// Animation with pulse\n",
            building_block + "\n// Animation with pulse\n",
        )

    # ── Inject building animation code into animate loop (scope:all only) ────
    if all_anim_lines:
        anim_block = "\n".join(all_anim_lines) + "\n"
        content = content.replace(
            "    controls.update();\n    renderer.render(scene, camera);",
            anim_block + "    controls.update();\n    renderer.render(scene, camera);",
        )

    return content

# ---------------------------------------------------------------------------
# Ocean with animated waves + low-poly fishing boats
# ---------------------------------------------------------------------------
def _replace_coast_points_in_content(content, coast_pts):
    """Replace the COAST_POINTS array in content with new dynamic values.

    Handles the exact format used in asturias-scene.js:
        const COAST_POINTS = [...].sort((a, b) => a[0] - b[0]);  // comment
    Returns (new_content, replaced_count).
    """
    coast_js = json.dumps(coast_pts)
    new_decl = f"const COAST_POINTS = {coast_js}.sort((a,b)=>a[0]-b[0]);"

    start_marker = "const COAST_POINTS = ["
    start_idx = content.find(start_marker)
    if start_idx == -1:
        return content, 0

    sort_idx = content.find("].sort(", start_idx)
    if sort_idx == -1:
        return content, 0

    semi_idx = content.find(";", sort_idx)
    if semi_idx == -1:
        return content, 0

    # Consume to end of line (skip trailing comments)
    nl_idx = content.find("\n", semi_idx)
    if nl_idx == -1:
        nl_idx = len(content)

    content = content[:start_idx] + new_decl + content[nl_idx:]
    return content, 1


def inject_ocean_and_boats(content, polygon_data):
    """Inject coast-aligned ocean and navigating boats with wakes.

    Two modes:
    - If COAST_POINTS already present in content (coast-aligned ocean from previous
      session): only update the COAST_POINTS array with dynamically-computed values.
    - Otherwise: inject flat ocean plane + boats (legacy fallback for fresh scene.js).
    """

    # --- Case A: Coast-aligned ocean already present → update COAST_POINTS ---
    if "COAST_POINTS" in content and "zCoastAt" in content:
        coast_pts = compute_coast_from_polygons(polygon_data)
        content, n = _replace_coast_points_in_content(content, coast_pts)
        if n:
            print(f"  Updated COAST_POINTS: {len(coast_pts)} dynamic points from polygon vertices")
            z_vals = [pt[1] for pt in coast_pts[1:-1]]  # exclude sentinels
            print(f"  Z range: {min(z_vals):.3f} – {max(z_vals):.3f}")
        else:
            print("  WARNING: COAST_POINTS found but replacement failed")
        return content

    # --- Case B: No coast-aligned code → inject flat ocean + boats (legacy) ---

    # --- 1. Object creation (ocean + boat factory + boat instances) ---
    obj = [
        "",
        "// --- Ocean (Mar Cantábrico) — flat color 0xa7d1f1 ---",
        "const oceanGeo = new THREE.PlaneGeometry(14, 3.5);",
        "const oceanMat = new THREE.MeshBasicMaterial({ color: 0xa7d1f1, side: THREE.DoubleSide });",
        "const ocean = new THREE.Mesh(oceanGeo, oceanMat);",
        "ocean.rotation.x = -Math.PI / 2;",
        f"ocean.position.set(0, -0.02, {OCEAN_Z});",
        "scene.add(ocean);",
        "",
        "// --- Low-poly fishing boats with wake ---",
        "function createBoat(hullColor, sailColor) {",
        "    const g = new THREE.Group();",
        "    // Hull shape (boat profile from above: pointed bow, wide stern)",
        "    const hs = new THREE.Shape();",
        "    hs.moveTo(0, 0.06);",
        "    hs.lineTo(0.02, 0.02);",
        "    hs.lineTo(0.025, -0.01);",
        "    hs.lineTo(0.02, -0.04);",
        "    hs.lineTo(0.008, -0.06);",
        "    hs.lineTo(-0.008, -0.06);",
        "    hs.lineTo(-0.02, -0.04);",
        "    hs.lineTo(-0.025, -0.01);",
        "    hs.lineTo(-0.02, 0.02);",
        "    const hGeo = new THREE.ExtrudeGeometry(hs, { depth: 0.012, bevelEnabled: false });",
        "    const hull = new THREE.Mesh(hGeo, new THREE.MeshLambertMaterial({ color: hullColor, flatShading: true }));",
        "    hull.rotation.x = -Math.PI / 2;",
        "    g.add(hull);",
        "    // Sail (triangle visible from above)",
        "    const ss = new THREE.Shape();",
        "    ss.moveTo(0, 0.035);",
        "    ss.lineTo(0.025, -0.015);",
        "    ss.lineTo(-0.005, -0.015);",
        "    const sail = new THREE.Mesh(new THREE.ShapeGeometry(ss),",
        "        new THREE.MeshLambertMaterial({ color: sailColor, side: THREE.DoubleSide }));",
        "    sail.rotation.x = -Math.PI / 2;",
        "    sail.position.y = 0.015;",
        "    g.add(sail);",
        "    // Mast (tiny cylinder, dot from above)",
        "    const mast = new THREE.Mesh(",
        "        new THREE.CylinderGeometry(0.003, 0.003, 0.06, 4),",
        "        new THREE.MeshLambertMaterial({ color: 0x4a3728 }));",
        "    mast.position.y = 0.03;",
        "    g.add(mast);",
        "    // Wake (V-shape behind boat)",
        "    const ws = new THREE.Shape();",
        "    ws.moveTo(0, -0.06);",
        "    ws.lineTo(-0.05, -0.30);",
        "    ws.lineTo(0, -0.22);",
        "    ws.lineTo(0.05, -0.30);",
        "    ws.closePath();",
        "    const wake = new THREE.Mesh(new THREE.ShapeGeometry(ws),",
        "        new THREE.MeshBasicMaterial({ color: 0xe8f4ff, transparent: true, opacity: 0.7, side: THREE.DoubleSide }));",
        "    wake.rotation.x = -Math.PI / 2;",
        "    wake.position.y = -0.005;",
        "    wake.name = 'wake';",
        "    g.add(wake);",
        "    return g;",
        "}",
        "",
        "const boats = [];",
    ]

    for cfg in BOAT_CONFIGS:
        bid = cfg["id"]
        obj.append(f"const {bid} = createBoat({cfg['hull']}, {cfg['sail']});")
        obj.append(f"{bid}.position.set({cfg['x']}, -0.02, {cfg['z']});")
        obj.append(f"{bid}.rotation.y = {cfg['rotY']};")
        obj.append(f"{bid}.scale.setScalar({cfg['scale']});")
        obj.append(f"scene.add({bid});")
        obj.append(
            f"boats.push({{ group: {bid}, baseZ: {cfg['z']}, "
            f"phase: {cfg['phase']}, speed: {cfg['speed']} }});"
        )

    obj.append("")
    objects_block = "\n".join(obj)

    content = content.replace(
        "// Animation with pulse\n",
        objects_block + "\n// Animation with pulse\n",
    )

    # --- 2. Animation code (foam vertex colors + boat navigation) ---
    anim = (
        "    // --- Boat navigation animation ---\n"
        "    boats.forEach(b => {\n"
        "        // Navigate along coast (X axis)\n"
        "        b.group.position.x += b.speed;\n"
        "        // Wrap around when out of view\n"
        "        if (b.speed > 0 && b.group.position.x > 7) b.group.position.x = -7;\n"
        "        if (b.speed < 0 && b.group.position.x < -7) b.group.position.x = 7;\n"
        "        // Gentle Z oscillation (approach/recede from coast)\n"
        "        b.group.position.z = b.baseZ + Math.sin(_t * 0.15 + b.phase) * 0.04;\n"
        "        // Subtle Y bobbing\n"
        "        b.group.position.y = -0.02 + Math.sin(_t * 1.2 + b.phase) * 0.004;\n"
        "        // Gentle roll and pitch\n"
        "        b.group.rotation.z = Math.sin(_t * 0.8 + b.phase) * 0.04;\n"
        "        b.group.rotation.x = Math.sin(_t * 0.6 + b.phase * 0.7) * 0.02;\n"
        "        // Heading wobble (simulates rudder corrections)\n"
        "        const baseHeading = b.speed > 0 ? -Math.PI/2 : Math.PI/2;\n"
        "        b.group.rotation.y = baseHeading + Math.sin(_t * 0.2 + b.phase) * 0.08;\n"
        "        // Animate wake opacity\n"
        "        const wake = b.group.getObjectByName('wake');\n"
        "        if (wake) wake.material.opacity = 0.55 + Math.sin(_t * 4.0 + b.phase) * 0.15;\n"
        "    });\n"
    )

    content = content.replace(
        "    controls.update();\n    renderer.render(scene, camera);",
        anim + "    controls.update();\n    renderer.render(scene, camera);",
    )

    print(f"  Ocean: PlaneGeometry(14, 3.5) at (0, -0.02, {OCEAN_Z}) — flat 0xa7d1f1")
    print(f"  Boats: {len(BOAT_CONFIGS)} navigating boats with wakes")

    return content


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    # Template lives inside app/ (canonical location)
    template_path   = PROJECT_ROOT / "app" / "static" / "js" / "asturias-scene.template.js"
    legacy_template = PROJECT_ROOT / "asturias_project" / "scene_template.js"  # old location
    scene_js_path   = PROJECT_ROOT / "asturias_project" / "scene.js"           # original 3D source
    output_path     = PROJECT_ROOT / "app" / "static" / "js" / "asturias-scene.js"

    # Priority: app/static/js/template > asturias_project/template > scene.js > in-place
    if template_path.exists():
        input_path = template_path
        is_template = True
    elif legacy_template.exists():
        input_path = legacy_template
        is_template = True
    elif scene_js_path.exists():
        input_path = scene_js_path
        is_template = False
    else:
        # Fallback: in-place COAST_POINTS update on the already-built file
        print(f"No source found ({template_path}).")
        print(f"In-place COAST_POINTS update of {output_path}...")
        content = output_path.read_text(encoding="utf-8")
        polygon_data = extract_polygon_data(content)
        print(f"  Found {len(polygon_data)} polygons")
        content = inject_ocean_and_boats(content, polygon_data)
        output_path.write_text(content, encoding="utf-8")
        print(f"\nDone! Updated: {output_path}")
        print(f"Size: {output_path.stat().st_size:,} bytes")
        return

    print(f"Reading {'template' if is_template else 'source'}: {input_path}...")
    content = input_path.read_text(encoding="utf-8")

    if is_template:
        # Template already has steps 1-12 applied.
        # Only run step 5 (for polygon_data needed by step 14), then 13 and 14.

        # 5. Extract polygon data (needed for COAST_POINTS computation in step 14)
        print("5. Extracting polygon data from template...")
        polygon_data = extract_polygon_data(content)
        print(f"  Found {len(polygon_data)} polygons")

        # 13. Inject scope:all buildings + generate municipality index.js modules
        print("13. Injecting scope:all buildings + generating municipality modules...")
        content = inject_buildings(content)
        generate_municipality_modules()

        # 14. Inject ocean with waves and boats (updates COAST_POINTS)
        print("14. Injecting ocean and boats...")
        content = inject_ocean_and_boats(content, polygon_data)

    else:
        # Full pipeline from scene.js source

        # 1. Import paths
        print("1. Fixing import paths...")
        content = content.replace(
            "from './vendor/three.module.js'",
            "from '/static/vendor/three/three.module.js'",
        )
        content = content.replace(
            "from './vendor/OrbitControls.js'",
            "from '/static/vendor/three/OrbitControls.js'",
        )

        # 2. Background color
        print("2. Replacing background color...")
        content = content.replace("0x1a6b8a", "0xa7d1f1")

        # 3. Material colors (random from 8 pastel colors, deterministic seed)
        print("3. Replacing material colors...")
        rng = random.Random(42)
        color_re = re.compile(r"(MeshLambertMaterial\(\{ color: )0x[0-9a-fA-F]{6}")
        color_counter = [0]

        def _replace_color(match):
            new_color = hex_css_to_threejs(rng.choice(PASTEL_PALETTE))
            color_counter[0] += 1
            return f"{match.group(1)}{new_color}"

        content = color_re.sub(_replace_color, content)
        print(f"  Replaced {color_counter[0]} material colors")

        # 3b. Add DoubleSide to polygon materials (visible laterals)
        print("3b. Adding DoubleSide to polygon materials...")
        content = add_polygon_doubleside(content)

        # 4. Quarter extrusion depths
        print("4. Quartering extrusion depths...")
        content = quarter_extrusion_depths(content)

        # 5. Extract polygon data (with halved depths)
        print("5. Extracting polygon data...")
        polygon_data = extract_polygon_data(content)
        print(f"  Found {len(polygon_data)} polygons")

        # 6. Build marker-polygon mapping
        print("6. Building marker-polygon mapping...")
        mapping = build_marker_polygon_mapping(content, polygon_data)
        marker_names = extract_marker_names(content)

        # 7. Replace marker positions with centroids
        print("7. Replacing marker positions with centroids...")
        content = replace_marker_positions_with_centroids(content, polygon_data, mapping)

        # 8. Shrink marker geometry
        print("8. Shrinking marker geometry...")
        content = shrink_marker_geometry(content)

        # 9. Fix raycaster for embedded container
        print("9. Fixing raycaster for embedded container...")
        content = fix_raycaster(content)

        # 10. Top-down camera (drone view)
        print("10. Setting top-down camera (drone view)...")
        content = set_topdown_camera(content)

        # 10b. Disable orbit rotation
        print("10b. Disabling orbit rotation...")
        content = disable_orbit_rotation(content)

        # 11. Handle orphan polygons
        print("11. Handling orphan polygons...")
        content = handle_orphan_polygons(content)

        # 12. Inject polygon interactivity (XZ expansion + centroid)
        print("12. Injecting polygon interactivity...")
        content = inject_polygon_interactivity(content, polygon_data, mapping, marker_names)

        # 13. Inject 3D buildings on platforms
        print("13. Injecting 3D buildings...")
        content = inject_buildings(content)

        # 14. Inject ocean with waves and boats
        print("14. Injecting ocean and boats...")
        content = inject_ocean_and_boats(content, polygon_data)

    # Replace BUILD_TS placeholder with current Unix timestamp (cache-busting)
    import time as _time
    build_ts = str(int(_time.time()))
    content = content.replace("BUILD_TS", build_ts)

    # Write output
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content, encoding="utf-8")
    print(f"\nDone! Output: {output_path}")
    print(f"Size: {output_path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
