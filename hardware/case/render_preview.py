#!/usr/bin/env python3
"""Aperçus PNG du boîtier, écrans allumés, touche et boutons en place.

Petit rendu maison (projection orthographique + tampon de profondeur) pour ne
dépendre que de numpy, Pillow et CadQuery.

    python3 hardware/case/render_preview.py      # écrit out/apercu.png
"""

import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFont

import hey_case as h

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
sys.path.insert(0, ROOT)

from hey.config import Config                       # noqa: E402
from hey.rear import RearRenderer                   # noqa: E402
from hey.render import Renderer                     # noqa: E402
from hey.state import Indicator                     # noqa: E402

BACKGROUND = (244, 244, 246)
SHELL = (52, 54, 60)
LID = (70, 74, 82)
PANEL = (16, 16, 18)
OLED_ON = (225, 235, 255)
CAPS = {"key": (236, 232, 222), "on_air": (215, 40, 35), "hey": (245, 190, 20),
        "urgency": (240, 110, 30), "switch": (190, 190, 196), "knob": (40, 40, 44)}


# --- géométrie ------------------------------------------------------------------
def triangles(shape, offset=(0.0, 0.0, 0.0), tolerance=0.1):
    vertices, faces = shape.val().tessellate(tolerance, 0.2)
    points = np.array([(v.x, v.y, v.z) for v in vertices]) + np.array(offset)
    return points[np.array(faces)]


def quads(cells, z, normal_sign):
    """Petits carrés plats (x0, y0, x1, y1, couleur) -> triangles et couleurs."""
    tris, colors = [], []
    for x0, y0, x1, y1, color in cells:
        a, b, c, d = (x0, y0, z), (x1, y0, z), (x1, y1, z), (x0, y1, z)
        if normal_sign < 0:                 # face tournée vers -Z (l'avant)
            tris += [(a, c, b), (a, d, c)]
        else:                               # face tournée vers +Z (l'arrière)
            tris += [(a, b, c), (a, c, d)]
        colors += [color, color]
    return np.array(tris, dtype=float), colors


def led_cells(image, pitch, dot=0.62):
    """LED de la dalle avant (face en z = FRONT_T + SMOKED_T, vue de devant)."""
    image = image.convert("RGB")
    cols, rows = image.size
    pixels = image.load()
    half = pitch * dot / 2
    cells = []
    for row in range(rows):
        for col in range(cols):
            color = pixels[col, row]
            if color == (0, 0, 0):
                color = (34, 34, 38)
            cx = (col - cols / 2 + 0.5) * pitch
            cy = (rows / 2 - row - 0.5) * pitch
            cells.append((cx - half, cy - half, cx + half, cy + half, color))
    return cells


def oled_cells(image):
    """Pixels allumés de l'OLED, vus de derrière (l'image est donc retournée en X)."""
    width, height = image.size
    active_w, active_h = 29.4, 14.7
    step_x, step_y = active_w / width, active_h / height
    pixels = image.convert("L").load()
    ox, oy = h.OLED_POS
    cells = [(ox - active_w / 2, oy - active_h / 2, ox + active_w / 2, oy + active_h / 2,
              (8, 8, 10))]
    for row in range(height):
        for col in range(width):
            if pixels[col, row]:
                # Vu de derrière, la gauche de l'image est à +X.
                x = ox + active_w / 2 - (col + 1) * step_x
                y = oy + active_h / 2 - (row + 1) * step_y
                cells.append((x, y, x + step_x, y + step_y, OLED_ON))
    return cells


def caps():
    """Capuchons des commandes (pour l'aperçu seulement)."""
    import cadquery as cq

    top = h.OUTER_H / 2
    parts = []
    for name, x in h.CONTROL_X.items():
        if name == "key":
            housing = (cq.Workplane("XZ").rect(14, 14).extrude(-6.6)
                       .translate((x, top, h.CTRL_Z)))
            parts.append((triangles(housing, tolerance=0.05), (60, 60, 66), False))
            shape = (cq.Workplane("XZ").rect(18, 18).workplane(offset=-8)
                     .rect(13, 13).loft()
                     .translate((x, top + 6.6, h.CTRL_Z)))
        elif name == "switch":
            shape = (cq.Workplane("XZ").circle(1.6).extrude(-11)
                     .rotate((0, 0, 0), (1, 0, 0), -20)
                     .translate((x, top, h.CTRL_Z)))
        else:
            shape = (cq.Workplane("XZ").circle(5.0).extrude(-4)
                     .faces(">Y").edges().fillet(1.2).translate((x, top, h.CTRL_Z)))
        parts.append((triangles(shape, tolerance=0.05), CAPS[name], False))
    knob = (cq.Workplane("YZ").circle(7.5).extrude(14).faces(">X").edges().fillet(1.5)
            .translate((h.OUTER_W / 2, 0, h.CTRL_Z)))
    parts.append((triangles(knob, tolerance=0.05), CAPS["knob"], False))
    return parts


def scene_parts(snap_front, snap_back, cover_offset=0.0):
    cfg = Config()
    leds = Renderer(cfg).render(snap_front, 0.0)
    rear = RearRenderer(cfg, "192.168.1.20").render(snap_back, 0.0)
    led_tris, led_colors = quads(led_cells(leds, cfg.pitch), h.FRONT_T + h.SMOKED_T - 0.05, -1)
    glass_z = h.BODY_D + h.COVER_T - h.OLED_SKIN + cover_offset + 0.05
    oled_tris, oled_colors = quads(oled_cells(rear), glass_z, +1)
    return [
        (triangles(h.make_body()), SHELL, False),
        (triangles(h.make_cover(), (0, 0, cover_offset)), LID, False),
        (triangles(h.make_panel()), PANEL, False),
        (led_tris, led_colors, True),
        (oled_tris, oled_colors, True),
    ] + caps()


# --- rendu ----------------------------------------------------------------------
def rotation(yaw, pitch):
    yaw, pitch = np.radians(yaw), np.radians(pitch)
    around_y = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
    around_x = np.array([[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)],
                         [0, np.sin(pitch), np.cos(pitch)]])
    return around_x @ around_y


def render(parts, yaw, pitch, center, scale, size):
    """`parts` : (triangles, couleur ou liste de couleurs, lumineux ?)."""
    width, height = size
    color = np.full((height, width, 3), BACKGROUND, dtype=np.float64)
    depth = np.full((height, width), np.inf)
    matrix = rotation(yaw, pitch)
    light = np.array([-0.35, 0.6, -0.72])
    light /= np.linalg.norm(light)
    for tris, base, emissive in parts:
        if len(tris) == 0:
            continue
        view = (tris - np.array(center)) @ matrix.T          # caméra : regarde vers +Z
        normals = np.cross(view[:, 1] - view[:, 0], view[:, 2] - view[:, 0])
        norms = np.linalg.norm(normals, axis=1)
        per_triangle = isinstance(base, list)
        for index, (tri, normal, norm) in enumerate(zip(view, normals, norms)):
            if norm < 1e-12:
                continue
            if emissive and normal[2] >= 0:                  # face lumineuse vue de dos
                continue
            tone = base[index] if per_triangle else base
            shade = 1.0 if emissive else 0.38 + 0.62 * abs(float(normal @ light) / norm)
            xs = tri[:, 0] * scale + width / 2
            ys = height / 2 - tri[:, 1] * scale
            x0, x1 = max(int(np.floor(xs.min())), 0), min(int(np.ceil(xs.max())), width - 1)
            y0, y1 = max(int(np.floor(ys.min())), 0), min(int(np.ceil(ys.max())), height - 1)
            if x0 > x1 or y0 > y1:
                continue
            area = (xs[1] - xs[0]) * (ys[2] - ys[0]) - (xs[2] - xs[0]) * (ys[1] - ys[0])
            if abs(area) < 1e-9:
                continue
            gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
            w0 = ((xs[1] - gx) * (ys[2] - gy) - (xs[2] - gx) * (ys[1] - gy)) / area
            w1 = ((xs[2] - gx) * (ys[0] - gy) - (xs[0] - gx) * (ys[2] - gy)) / area
            w2 = 1.0 - w0 - w1
            inside = (w0 >= -1e-6) & (w1 >= -1e-6) & (w2 >= -1e-6)
            z = w0 * tri[0, 2] + w1 * tri[1, 2] + w2 * tri[2, 2]
            if emissive:
                z = z - 0.02                                  # devant la surface porteuse
            region = depth[y0:y1 + 1, x0:x1 + 1]
            visible = inside & (z < region)
            region[visible] = z[visible]
            color[y0:y1 + 1, x0:x1 + 1][visible] = np.array(tone) * shade
    return Image.fromarray(np.clip(color, 0, 255).astype(np.uint8))


def snapshots():
    cfg = Config()
    front = Indicator(cfg)
    front.set_mode("busy")
    back = Indicator(cfg)
    back.set_mode("busy")
    back.timer_start()
    return front.snapshot(), back.snapshot()


def label_font(size=18):
    for path in ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
                 "/usr/share/fonts/TTF/DejaVuSans.ttf"):
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:                       # Pillow < 10.1
        return ImageFont.load_default()


def label(image, text, xy=(16, 12)):
    ImageDraw.Draw(image).text(xy, text, fill=(40, 40, 44), font=label_font())


def main():
    out_root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out")
    snap_front, snap_back = snapshots()
    parts = scene_parts(snap_front, snap_back)
    middle = (0, 0, (h.BODY_D + h.COVER_T) / 2)
    size = (900, 620)
    scale = 0.62 * size[0] / h.OUTER_W
    front = render(parts, yaw=28, pitch=-24, center=middle, scale=scale, size=size)
    back = render(parts, yaw=205, pitch=-24, center=middle, scale=scale, size=size)
    sheet = Image.new("RGB", (size[0] * 2, size[1]), BACKGROUND)
    sheet.paste(front, (0, 0))
    sheet.paste(back, (size[0], 0))
    label(sheet, "%.0f x %.0f x %.0f mm   (avant / arrière)"
          % (h.OUTER_W, h.OUTER_H, h.BODY_D + h.COVER_T))
    os.makedirs(out_root, exist_ok=True)
    path = os.path.join(out_root, "apercu.png")
    sheet.save(path)
    print(path)


if __name__ == "__main__":
    main()
