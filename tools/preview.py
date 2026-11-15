#!/usr/bin/env python3
"""Génère les aperçus PNG des écrans (docs/screens/), sans matériel.

    python3 tools/preview.py

docs/screens/           écran avant
docs/screens/arriere/   écran arrière OLED
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image

from hey.config import Config
from hey.display import save_png
from hey.rear import RearRenderer
from hey.render import Renderer

OLED_TINT = (225, 235, 255)
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


def main():
    root = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "docs", "screens")
    cfg = Config()
    renderer = Renderer(cfg)
    images = [(name, renderer.render(snap, t)) for name, snap, t in scenes(cfg)]
    print("avant : %d écrans" % write_set(root, images))

    rear = RearRenderer(cfg, "192.168.1.20")
    images = [(name, rear.render(snap, t)) for name, snap, t in scenes(cfg)]
    write_set(os.path.join(root, "arriere"), images, zoom=4, gap=1, tint=OLED_TINT)
    print("arrière : %d écrans" % len(images))
    print("écrits dans", os.path.normpath(root))


if __name__ == "__main__":
    main()
