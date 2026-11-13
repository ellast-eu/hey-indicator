#!/usr/bin/env python3
"""Aperçu PNG du boîtier : vue avant assemblée, vue arrière capot écarté.

Petit rendu maison (projection orthographique + tampon de profondeur) pour ne
dépendre que de numpy et Pillow.

    python3 hardware/case/render_preview.py
"""

import os

import numpy as np
from PIL import Image

import hey_case as h

SIZE = (900, 620)
SCALE = 3.6                     # pixels par millimètre
BACKGROUND = (244, 244, 246)


def triangles(shape, offset=(0.0, 0.0, 0.0)):
    vertices, faces = shape.val().tessellate(0.1, 0.2)
    points = np.array([(v.x, v.y, v.z) for v in vertices]) + np.array(offset)
    return points[np.array(faces)]


def rotation(yaw, pitch):
    """Tourne le modèle autour de la verticale (Y) puis bascule la vue."""
    yaw, pitch = np.radians(yaw), np.radians(pitch)
    around_y = np.array([[np.cos(yaw), 0, np.sin(yaw)], [0, 1, 0], [-np.sin(yaw), 0, np.cos(yaw)]])
    around_x = np.array([[1, 0, 0], [0, np.cos(pitch), -np.sin(pitch)],
                         [0, np.sin(pitch), np.cos(pitch)]])
    return around_x @ around_y


def render(parts, yaw, pitch, center):
    width, height = SIZE
    color = np.full((height, width, 3), BACKGROUND, dtype=np.float64)
    depth = np.full((height, width), np.inf)
    matrix = rotation(yaw, pitch)
    light = np.array([-0.35, 0.55, -0.75])
    light /= np.linalg.norm(light)
    for tris, base in parts:
        view = (tris - np.array(center)) @ matrix.T       # caméra : regarde vers +Z
        normals = np.cross(view[:, 1] - view[:, 0], view[:, 2] - view[:, 0])
        norms = np.linalg.norm(normals, axis=1)
        for tri, normal, norm in zip(view, normals, norms):
            if norm < 1e-9:
                continue
            shade = 0.35 + 0.65 * abs(float(normal @ light) / norm)
            xs = tri[:, 0] * SCALE + width / 2
            ys = height / 2 - tri[:, 1] * SCALE
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
            region = depth[y0:y1 + 1, x0:x1 + 1]
            visible = inside & (z < region)
            region[visible] = z[visible]
            color[y0:y1 + 1, x0:x1 + 1][visible] = np.array(base) * shade
    return Image.fromarray(np.clip(color, 0, 255).astype(np.uint8))


def main():
    body, cover, panel = h.make_body(), h.make_cover(), h.make_panel()
    shell, lid, dark = (235, 120, 40), (150, 165, 190), (18, 18, 22)
    middle = (0, 0, (h.BODY_D + h.COVER_T) / 2)
    front = render([(triangles(body), shell), (triangles(cover), shell), (triangles(panel), dark)],
                   yaw=32, pitch=-22, center=middle)
    back = render([(triangles(body), shell), (triangles(panel), dark),
                   (triangles(cover, (0, 0, 45)), lid)],
                  yaw=215, pitch=-22, center=(0, 0, middle[2] + 20))
    sheet = Image.new("RGB", (SIZE[0] * 2, SIZE[1]), BACKGROUND)
    sheet.paste(front, (0, 0))
    sheet.paste(back, (SIZE[0], 0))
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", "apercu.png")
    sheet.save(out)
    print(out)


if __name__ == "__main__":
    main()
