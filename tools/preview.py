#!/usr/bin/env python3
"""Génère un aperçu PNG de chaque écran (docs/screens/), sans matériel.

    python3 tools/preview.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from PIL import Image

from hey.config import Config
from hey.display import save_png
from hey.render import Renderer
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


def main():
    cfg = Config()
    renderer = Renderer(cfg)
    out_dir = os.path.join(os.path.dirname(__file__), "..", "docs", "screens")
    os.makedirs(out_dir, exist_ok=True)
    paths = []
    for name, snap, t in scenes(cfg):
        path = os.path.join(out_dir, name + ".png")
        save_png(renderer.render(snap, t), path)
        paths.append(path)

    tiles = [Image.open(p) for p in paths]
    width, height = tiles[0].size
    pad = 16
    sheet = Image.new("RGB", (2 * width + 3 * pad, 5 * height + 6 * pad), (40, 40, 44))
    for index, tile in enumerate(tiles):
        sheet.paste(tile, (pad + (index % 2) * (width + pad), pad + (index // 2) * (height + pad)))
    sheet.save(os.path.join(out_dir, "planche.png"))
    print("%d écrans écrits dans %s" % (len(paths), os.path.normpath(out_dir)))


if __name__ == "__main__":
    main()
