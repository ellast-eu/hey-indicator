#!/usr/bin/env python3
"""Génère les aperçus PNG des écrans (docs/screens/), sans matériel.

    python3 tools/preview.py

docs/screens/<dalle>/   écrans avant, pour chaque dalle connue
docs/screens/arriere/   écran arrière OLED
docs/screens/echelle.png  les deux dalles et l'OLED à la même échelle
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image, ImageDraw, ImageFont

from hey.config import PANELS, Config
from hey.display import save_png
from hey.rear import RearRenderer
from hey.render import Renderer

OLED_TINT = (225, 235, 255)
OLED_ACTIVE_MM = (29.4, 14.7)       # zone active d'un OLED 1,3" 128x64 courant
from hey.state import Indicator


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def scenes(cfg):
    """(nom, instantané, temps d'animation) pour chaque écran."""
    clock = FakeClock()

    def fresh():
        return Indicator(cfg, clock)

    ind = fresh()
    yield "1-free", ind.snapshot(), 0.0
    ind.set_mode("busy")
    yield "2-busy", ind.snapshot(), 0.0

    ind = fresh()
    ind.set_on_air(True)
    clock.now += 754
    yield "3-on-air", ind.snapshot(), 0.0

    ind = fresh()
    ind.adjust(+5)
    yield "4-reglage", ind.snapshot(), 0.0

    ind = fresh()
    ind.timer_start()
    clock.now += 421
    yield "5-focus", ind.snapshot(), 0.0
    clock.now += 25 * 60 - 421 + 72
    ind.tick()
    yield "6-break", ind.snapshot(), 0.0

    ind = fresh()
    ind.hey()
    yield "7-hey", ind.snapshot(), 0.25
    ind.hey("Réunion dans 5 min ?")
    yield "8-hey-message", ind.snapshot(), 2.2

    ind = fresh()
    ind.urgency()
    yield "9-urgent-a", ind.snapshot(), 0.0
    yield "9-urgent-b", ind.snapshot(), 0.3


def sheet(paths, out_path, columns=2):
    tiles = [Image.open(p) for p in paths]
    width, height = tiles[0].size
    pad = 16
    lines = (len(tiles) + columns - 1) // columns
    board = Image.new("RGB", (columns * width + (columns + 1) * pad,
                              lines * height + (lines + 1) * pad), (40, 40, 44))
    for index, tile in enumerate(tiles):
        board.paste(tile, (pad + (index % columns) * (width + pad),
                           pad + (index // columns) * (height + pad)))
    board.save(out_path)


def write_set(out_dir, images, **png_options):
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name, image in images:
        path = os.path.join(out_dir, name + ".png")
        save_png(image, path, **png_options)
        paths.append(path)
    sheet(paths, os.path.join(out_dir, "planche.png"))
    return len(paths)


def physical(image, pitch_mm, px_per_mm, tint=None, dot=0.62, background=(12, 12, 14)):
    """Dessine un écran à sa taille réelle (`px_per_mm` pixels par mm)."""
    image = image.convert("RGB")
    width, height = image.size
    step = pitch_mm * px_per_mm
    board = Image.new("RGB", (round(width * step), round(height * step)), background)
    draw = ImageDraw.Draw(board)
    pixels = image.load()
    radius = step * dot / 2
    for y in range(height):
        for x in range(width):
            color = pixels[x, y]
            if color == (0, 0, 0):
                color = (28, 28, 32)
            elif tint:
                color = tint
            cx, cy = (x + 0.5) * step, (y + 0.5) * step
            if tint:                        # OLED : pixels jointifs
                draw.rectangle((cx - step / 2, cy - step / 2, cx + step / 2, cy + step / 2),
                               fill=color)
            else:
                draw.ellipse((cx - radius, cy - radius, cx + radius, cy + radius), fill=color)
    return board


def scale_comparison(out_path, px_per_mm=3.0):
    """Les deux dalles en BUSY, et l'écran arrière, à la même échelle."""
    pad = 30
    boards = []
    for panel in sorted(PANELS):
        cfg = Config(panel=panel)
        ind = Indicator(cfg, FakeClock())
        ind.set_mode("busy")
        boards.append((panel, cfg, physical(Renderer(cfg).render(ind.snapshot(), 0.0),
                                            cfg.pitch, px_per_mm)))
    cfg = Config()
    ind = Indicator(cfg, FakeClock())
    ind.set_mode("busy")
    ind.timer_start()
    rear = RearRenderer(cfg, "192.168.1.20").render(ind.snapshot(), 0.0)
    oled = physical(rear, OLED_ACTIVE_MM[0] / 128, px_per_mm, tint=OLED_TINT)

    width = sum(b.size[0] for _, _, b in boards) + oled.size[0] + pad * (len(boards) + 2)
    height = max(b.size[1] for _, _, b in boards) + pad * 2 + 30
    canvas = Image.new("RGB", (round(width), height), (244, 244, 246))
    draw = ImageDraw.Draw(canvas)
    try:
        label_font = ImageFont.load_default(size=16)
    except TypeError:                       # Pillow < 10.1
        label_font = ImageFont.load_default()
    x = pad
    for panel, cfg, board in boards:
        canvas.paste(board, (x, pad))
        draw.text((x, pad + board.size[1] + 8), "%s  pas %.1f mm  %d x %d mm"
                  % (panel, cfg.pitch, cfg.cols * cfg.pitch, cfg.rows * cfg.pitch),
                  fill=(40, 40, 44), font=label_font)
        x += board.size[0] + pad
    canvas.paste(oled, (x, pad))
    draw.text((x, pad + oled.size[1] + 8), "OLED 1,3\"", fill=(40, 40, 44),
              font=label_font)
    canvas.save(out_path)


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "screens")
    for panel in sorted(PANELS):
        cfg = Config(panel=panel)
        renderer = Renderer(cfg)
        images = [(name, renderer.render(snap, t)) for name, snap, t in scenes(cfg)]
        count = write_set(os.path.join(root, panel), images)
        print("%s : %d écrans" % (panel, count))

    cfg = Config()
    rear = RearRenderer(cfg, "192.168.1.20")
    images = [(name, rear.render(snap, t)) for name, snap, t in scenes(cfg)]
    write_set(os.path.join(root, "arriere"), images, zoom=4, gap=1, tint=OLED_TINT)
    print("arrière : %d écrans" % len(images))

    scale_comparison(os.path.join(root, "echelle.png"))
    print("écrits dans", os.path.normpath(root))


if __name__ == "__main__":
    main()
