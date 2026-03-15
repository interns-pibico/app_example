#!/usr/bin/env python3
"""
Convert laLaboral JS scene script to JSON building definition.

Transform (confirmed from existing JSON):
  x_json  = x_scene  * S
  y_json  = (y_scene - 1) * S
  z_json  = (z_scene - 14) * S
  sizes   = size * S
  S = 0.0020
"""

import json
import math
import os

S = 0.0020

# Camera/reference positions from JS
IX, IZ = -2, -4    # church
TX, TZ = -10, -22  # clock tower
RX, RZ = 0, -58    # rotonda


def tx(x):
    return round(x * S, 6)

def ty(y):
    return round((y - 1) * S, 6)

def tz(z):
    return round((z - 14) * S, 6)

def ts(s):
    return round(s * S, 6)


# Material → color mapping (None = base color, no override)
COLORS = {
    "stone":  None,
    "stone2": "0xb89040",
    "roof":   "0x4a5460",
    "roofDk": "0x333f4a",
    "white":  "0xd5cdc0",
    "win":    "0x1a2028",
    "court":  "0x706858",
    "copper": "0x4a7060",
    "dark":   "0x222018",
    "stair":  "0x807060",
    "clock":  "0xe8e0d0",
    "trunk":  "0x3a2510",
    "foliage": "0x1e3010",
}

parts = []


def _part(p, mat):
    c = COLORS.get(mat)
    if c:
        p["color"] = c
    parts.append(p)


def box(w, h, d, mat, x, y, z, ry=None):
    p = {
        "geometry": "box",
        "params": {"width": ts(w), "height": ts(h), "depth": ts(d)},
        "position": [tx(x), ty(y), tz(z)],
    }
    if ry is not None:
        p["rotation"] = {"y": round(ry, 5)}
    _part(p, mat)


def cyl(rt, rb, h, seg, mat, x, y, z, rotation=None):
    p = {
        "geometry": "cylinder",
        "params": {
            "radiusTop": ts(rt),
            "radiusBottom": ts(rb),
            "height": ts(h),
            "radialSegments": seg,
        },
        "position": [tx(x), ty(y), tz(z)],
    }
    if rotation:
        p["rotation"] = rotation
    _part(p, mat)


def cone(r, h, seg, mat, x, y, z, ry=None):
    p = {
        "geometry": "cone",
        "params": {"radius": ts(r), "height": ts(h), "radialSegments": seg},
        "position": [tx(x), ty(y), tz(z)],
    }
    if ry is not None:
        p["rotation"] = {"y": round(ry, 5)}
    _part(p, mat)


def torus(radius, tube, rad_seg, tub_seg, arc_expr, mat, x, y, z, rotation=None):
    p = {
        "geometry": "torus",
        "params": {
            "radius": ts(radius),
            "tube": ts(tube),
            "radialSegments": rad_seg,
            "tubularSegments": tub_seg,
            "arc": arc_expr,
        },
        "position": [tx(x), ty(y), tz(z)],
    }
    if rotation:
        p["rotation"] = rotation
    _part(p, mat)


def circle_cyl(r, seg, mat, x, y, z, rotation):
    """CircleGeometry → thin cylinder."""
    p = {
        "geometry": "cylinder",
        "params": {
            "radiusTop": ts(r),
            "radiusBottom": ts(r),
            "height": 0.0011,
            "radialSegments": seg,
        },
        "position": [tx(x), ty(y), tz(z)],
        "rotation": rotation,
    }
    _part(p, mat)


def tree(x, z, h=4.5):
    """Tree: trunk cylinder + foliage cone-cylinder."""
    cyl(0.22, 0.28, h * 0.4, 6, "trunk",   x, h * 0.2, z)
    cyl(0.00, h * 0.7, h * 0.8, 7, "foliage", x, h * 0.6, z)


# ═══════════════════════════════════════════════════════
#  PATIOS (pavimento)
# ═══════════════════════════════════════════════════════

# Patio central
box(36, 0.3, 38, "court", 0, 1.15, 14)
# Patio norte (entre bloque central y cierre norte)
box(34, 0.3, 22, "court", 0, 1.15, -27)

# ═══════════════════════════════════════════════════════
#  ZONA SUR — Fachada principal
# ═══════════════════════════════════════════════════════

# Cuerpo principal fachada
box(52, 10, 9, "stone", 0, 6, 47)
box(53, 1.5, 10, "roof", 0, 11.4, 47)

# Pabellones esquina sur
box(11, 12, 10, "stone", -31, 7, 47)
box(11, 12, 10, "stone",  31, 7, 47)
cone(8, 5, 4, "roof", -31, 13.5, 47, ry=math.pi / 4)
cone(8, 5, 4, "roof",  31, 13.5, 47, ry=math.pi / 4)

# Entrada principal
box(10, 14, 6, "stone", 0, 8, 51)
box(10.5, 2, 6.5, "roof", 0, 15.2, 51)
# Arco de entrada  TorusGeometry(2.4, 0.4, 8, 18, Math.PI)
torus(2.4, 0.4, 8, 18, "Math.PI", "white", 0, 5, 53.2,
      rotation={"x": round(math.pi, 5)})
# Ventana entrada
box(4, 5, 0.5, "win", 0, 3, 53.3)
# Frontón sobre entrada
cone(5.5, 3.5, 4, "stone", 0, 17.2, 51, ry=math.pi / 4)

# Alas laterales sur (conectan fachada con cuerpo central)
box(9, 9, 40, "stone", -22, 5.5, 27)
box(9.5, 1.3, 41, "roof", -22, 10.4, 27)
box(9, 9, 40, "stone",  22, 5.5, 27)
box(9.5, 1.3, 41, "roof",  22, 10.4, 27)

# Pabellones esquina del patio (4 esquinas)
for cx, cz in [(-22, 47), (-22, 7), (22, 47), (22, 7)]:
    box(10, 10, 10, "stone", cx, 6, cz)
    cone(7.5, 5, 4, "roof", cx, 11.5, cz, ry=math.pi / 4)

# Pináculos en tejados de las alas (pz=12,20,28,36 → 4 valores)
for pz in range(12, 43, 8):
    for px, ppz in [(-22, pz), (22, pz)]:
        cyl(0.25, 0.35, 1.5, 6, "stone", px, 11.5, ppz)
        cone(0.28, 1.4, 4, "roof", px, 12.7, ppz)

# ═══════════════════════════════════════════════════════
#  ZONA CENTRAL
# ═══════════════════════════════════════════════════════

# Bloque central elevado (cierra el patio por el norte)
box(52, 13, 12, "stone", 0, 7.5, -8)
box(53, 1.8, 13, "roof", 0, 14.2, -8)

# Coronación — pináculos en línea (px=-24,-18,...,24 → 9 valores)
for ipx in range(-24, 25, 6):
    cyl(0.25, 0.4, 1.5, 6, "stone", ipx, 15.3, -8)
    cone(0.3, 1.5, 4, "roof", ipx, 16.6, -8)

# Galería porticada entre bloque central y patio
box(38, 8, 5, "stone", 0, 5, -2)
box(39, 1, 5.5, "roof", 0, 9.2, -2)
# Pilares de la galería (px=-17,-12,-7,-2,3,8,13 → 7 valores)
for ipx in range(-17, 18, 5):
    cyl(0.55, 0.55, 7, 8, "white", ipx, 4.5, -2)

# ═══════════════════════════════════════════════════════
#  IGLESIA / PARANINFO
# ═══════════════════════════════════════════════════════
# IX=-2, IZ=-4 (ligeramente oeste, delante del bloque central)

# Cuerpo cilíndrico bajo
cyl(9.5, 10, 14, 12, "stone",  IX, 8, IZ)
# Tambor
cyl(8.5, 9.5, 4, 12, "stone",  IX, 15.5, IZ)
# Cúpula
cyl(1, 9, 4.5, 12, "roofDk",  IX, 18.8, IZ)
# Linterna
cyl(1.2, 2, 3, 10, "white",   IX, 21.5, IZ)
cone(0.8, 2, 10, "stone",     IX, 23.2, IZ)

# Pórtico iglesia
box(15, 12, 5, "stone", IX, 7, IZ + 8)
# Columnas pórtico (px=-5.5,-2,1.5,5 → 4 columnas)
for ipx in [-5.5, -2.0, 1.5, 5.0]:
    cyl(0.6, 0.6, 11, 8, "white", IX + ipx, 6.5, IZ + 10.5)
# Frontón sobre pórtico
cone(8, 4, 4, "stone", IX, 14.2, IZ + 8, ry=math.pi / 4)

# ═══════════════════════════════════════════════════════
#  ZONA NORTE — Torre y edificios del norte
# ═══════════════════════════════════════════════════════

# Alas norte
box(9, 10, 28, "stone", -22, 6, -27)
box(9.5, 1.3, 29, "roof", -22, 11.3, -27)
box(9, 10, 28, "stone",  22, 6, -27)
box(9.5, 1.3, 29, "roof",  22, 11.3, -27)

# Pabellones esquina norte (4)
for cx, cz in [(-22, -13), (22, -13), (-22, -41), (22, -41)]:
    box(10, 11, 10, "stone", cx, 6.5, cz)
    cone(7.5, 5, 4, "roof", cx, 12, cz, ry=math.pi / 4)

# Bloque de cierre norte
box(52, 10, 10, "stone", 0, 6, -41)
box(53, 1.5, 11, "roof", 0, 11.3, -41)

# Pináculos alas norte (pz=-18,-26,-34 → 3 valores)
for pz in range(-18, -39, -8):
    for px, ppz in [(-22, pz), (22, pz)]:
        cyl(0.25, 0.35, 1.5, 6, "stone", px, 12.5, ppz)
        cone(0.28, 1.4, 4, "roof", px, 13.7, ppz)

# ═══════════════════════════════════════════════════════
#  TORRE DEL RELOJ  TX=-10, TZ=-22
# ═══════════════════════════════════════════════════════

box(8, 6, 8, "stone", TX, 4, TZ)    # base maciza
box(7, 8, 7, "stone", TX, 12, TZ)   # cuerpo 1
box(6, 7, 6, "stone", TX, 19.5, TZ) # cuerpo 2
box(5, 6, 5, "stone", TX, 26.5, TZ) # cuerpo 3 (con reloj)

# Caras del reloj: CircleGeometry(1,16) → thin cylinder
# Para que la cara plana mire en la dirección correcta,
# rotamos el cilindro (eje Y→Z con rx=π/2, o eje Y→X con rz=π/2)
circle_cyl(1, 16, "clock", TX,        26.5, TZ + 2.55,
           rotation={"x": round(math.pi / 2, 5)})          # sur  (+Z)
circle_cyl(1, 16, "clock", TX,        26.5, TZ - 2.55,
           rotation={"x": round(math.pi / 2, 5)})          # norte (-Z)
circle_cyl(1, 16, "clock", TX + 2.55, 26.5, TZ,
           rotation={"z": round(math.pi / 2, 5)})          # este (+X)
circle_cyl(1, 16, "clock", TX - 2.55, 26.5, TZ,
           rotation={"z": round(math.pi / 2, 5)})          # oeste (-X)

# Campanario
box(4, 5.5, 4, "stone", TX, 32.5, TZ)

# Arcos campanario: TorusGeometry(0.9,0.18,6,12,Math.PI) ×4
for a in range(4):
    angle = a * math.pi / 2
    ax = TX + math.sin(angle) * 2.1
    az = TZ + math.cos(angle) * 2.1
    torus(0.9, 0.18, 6, 12, "Math.PI", "stone2", ax, 34, az,
          rotation={"x": round(math.pi, 5), "y": round(a * math.pi / 2, 5)})

# Remate torre
cyl(0.6, 2.5, 2.5, 8, "stone",  TX, 36.3, TZ)
cyl(0.15, 0.6, 5,  8, "roof",   TX, 39.5, TZ)
cyl(0.05, 0.15, 3, 6, "stone2", TX, 42.5, TZ)

# ═══════════════════════════════════════════════════════
#  ROTONDA CIRCULAR  RX=0, RZ=-58
# ═══════════════════════════════════════════════════════

# Pasarela de conexión
box(10, 7, 8, "stone", RX, 4.5, -48)
box(10.5, 1, 8.5, "roof", RX, 8.2, -48)

# Cuerpo cilíndrico principal
cyl(11, 11, 11, 24, "stone",   RX, 7,    RZ)
cyl(11.2, 11.2, 3, 24, "stone2", RX, 10.5, RZ)
cyl(0.8, 12, 3, 24, "roofDk",  RX, 13.5, RZ)

# Columnata exterior (20 columnas)
for i in range(20):
    a = (i / 20) * math.pi * 2
    col_x = RX + math.cos(a) * 13
    col_z = RZ + math.sin(a) * 13
    cyl(0.45, 0.45, 9, 8, "white", col_x, 5.5, col_z)

# Entablamento sobre columnas
cyl(13.5, 13.5, 0.8, 24, "white", RX, 10.2, RZ)

# Linterna superior
cyl(2, 3, 2.5, 12, "white", RX, 15.2, RZ)
cone(2, 2, 12, "roof",      RX, 17.1, RZ)

# ═══════════════════════════════════════════════════════
#  EDIFICIOS EXTERIORES
# ═══════════════════════════════════════════════════════

# Edificio Oeste largo ⑩
box(14, 9, 55, "stone", -45, 5.5, 8)
box(15, 1.3, 56, "roof", -45, 10.4, 8)
box(12, 11, 12, "stone", -45, 6.5,  35)
box(12, 11, 12, "stone", -45, 6.5, -18)
cone(9, 5.5, 4, "roof", -45, 12.3,  35, ry=math.pi / 4)
cone(9, 5.5, 4, "roof", -45, 12.3, -18, ry=math.pi / 4)

# Ventanas edificio oeste (pz=20,15,10,5,0,-5 → 6×2=12 ventanas)
for pz in [20, 15, 10, 5, 0, -5]:
    box(0.3, 2,   1.6, "win", -52.5, 6.5, pz)
    box(0.3, 1.6, 1.6, "win", -52.5, 9.2, pz)

# Edificio Sureste ⑫
box(16, 9, 16, "stone", 42, 5.5, 42)
box(16.5, 1.2, 16.5, "roof", 42, 10.3, 42)
cyl(3, 3.3, 3.5, 12, "stone",  42, 12.8, 42)
cyl(0.3, 3, 2, 12,  "copper",  42, 15.1, 42)
cone(0.5, 2, 8,     "stone",   42, 16.6, 42)

# Edificio Suroeste ⑪
box(14, 8, 14, "stone", -42, 5, 50)
box(14.5, 1.2, 14.5, "roof", -42, 9.3, 50)
cone(8, 4.5, 4, "roof", -42, 10.5, 50, ry=math.pi / 4)

# Bloque Noreste secundario
box(18, 9, 18, "stone", 38, 5.5, -35)
box(19, 1.2, 19, "roof", 38, 10.3, -35)
cone(10, 5, 4, "roof",   38, 11.5, -35, ry=math.pi / 4)

# ═══════════════════════════════════════════════════════
#  VENTANAS — Fachada sur
#  for(let px=-23;px<=23;px+=4.5) skip |px|<6
#  included: -23,-18.5,-14,-9.5, 8.5,13,17.5,22  (8 posiciones × 3 = 24)
# ═══════════════════════════════════════════════════════
for px in [-23.0, -18.5, -14.0, -9.5, 8.5, 13.0, 17.5, 22.0]:
    box(2, 2.5, 0.35, "win", px,  8,   51.7)
    box(2, 2.5, 0.35, "win", px,  4.8, 51.7)
    box(2, 1.8, 0.35, "win", px, 11,   51.7)

# Ventanas alas patio (exterior)
# for(let pz=12;pz<=42;pz+=4.5) → 12,16.5,21,25.5,30,34.5,39  (7 × 2 lados × 2 = 28)
for pz in [12.0, 16.5, 21.0, 25.5, 30.0, 34.5, 39.0]:
    for xside in [-26.5, 26.5]:
        box(0.35, 2,   2, "win", xside, 6, pz)
        box(0.35, 1.8, 2, "win", xside, 9, pz)

# ═══════════════════════════════════════════════════════
#  ÁRBOLES Y JARDINES  (alturas fijas — sin Math.random)
# ═══════════════════════════════════════════════════════

# Jardines laterales del patio (pz=10,17,24,31,38 — 5 pos × 2 lados)
for pz in range(10, 45, 7):
    tree(-30, pz, 4.5)
    tree( 30, pz, 4.5)

# Jardines norte (pz=-14,-21,-28,-35 — 4 pos × 2 lados)
for pz in range(-14, -37, -7):
    tree(-28, pz, 3.75)
    tree( 28, pz, 3.75)

# Jardines alrededor de la rotonda (10 árboles)
for i in range(10):
    a = (i / 10) * math.pi * 2
    tree(RX + math.cos(a) * 18, RZ + math.sin(a) * 18, 3.75)

# Jardines fachada sur (6 árboles)
for px in [-30, -20, -10, 10, 20, 30]:
    tree(px, 60, 3.75)

# Edificio oeste (pz=15,9,3,-3,-9,-15 — 6 pos × 2 lados)
for px in [-50, -48]:
    for pz in range(15, -16, -6):
        tree(px, pz, 4.0)


# ═══════════════════════════════════════════════════════
#  Escribir JSON
# ═══════════════════════════════════════════════════════
script_dir = os.path.dirname(os.path.abspath(__file__))
json_path = os.path.join(script_dir, "..", "app", "static", "js", "gijon", "laLaboral.json")
json_path = os.path.normpath(json_path)

with open(json_path) as f:
    existing = json.load(f)

existing["parts"] = parts

with open(json_path, "w") as f:
    json.dump(existing, f, indent=2)

print(f"Escrito {len(parts)} partes en {json_path}")

# Summary by type
from collections import Counter
geo_count = Counter(p["geometry"] for p in parts)
print("Tipos:", dict(geo_count))
