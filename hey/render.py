"""Dessin des écrans : un instantané d'état -> une image PIL 64x32.

Aucune dépendance au matériel : la même image part vers la dalle HUB75 ou
vers le simulateur.
"""

import math
import time

from PIL import Image

from . import font

BLACK = (0, 0, 0)


def _scale(color, factor):
    return tuple(max(0, min(255, int(c * factor))) for c in color)


def _mmss(seconds):
    seconds = int(math.ceil(seconds))
    return "%02d:%02d" % (seconds // 60, seconds % 60)


class Renderer:
    def __init__(self, cfg):
        self.cfg = cfg
        self.size = (cfg.cols, cfg.rows)

    # --- primitives ---------------------------------------------------------------
    def _text(self, image, text, y, color, sx=1, sy=None, x=None, gap=None):
        sy = sx if sy is None else sy
        if x is None:
            x = (self.size[0] - font.text_width(text, sx, gap)) // 2
        font.draw_text(image.load(), x, y, text, color, sx, sy, gap, size=self.size)

    def _big(self, image, text, y, color, wanted=2):
        """Texte principal à l'échelle `wanted` ; s'il déborde, on resserre
        d'abord l'espace entre lettres, puis on réduit l'échelle."""
        for scale in range(wanted, 0, -1):
            for gap in (scale, 1):
                if font.text_width(text, scale, gap) <= self.size[0]:
                    self._text(image, text, y, color, sx=scale, gap=gap)
                    return
        self._text(image, text, y, color, sx=1)

    def _bar(self, image, fraction, color):
        width, height = self.size
        lit = int(round(max(0.0, min(1.0, fraction)) * width))
        pixels = image.load()
        for x in range(width):
            for y in (height - 2, height - 1):
                pixels[x, y] = color if x < lit else _scale(color, 0.15)

    def _clock(self, image, y, color):
        self._text(image, time.strftime("%H:%M"), y, color)

    # --- écrans -------------------------------------------------------------------
    def render(self, snap, t=None):
        """`t` : temps d'animation en secondes (time.monotonic() par défaut)."""
        t = time.monotonic() if t is None else t
        image = Image.new("RGB", self.size, BLACK)
        getattr(self, "_screen_" + snap["screen"])(image, snap, t)
        return image

    def _status(self, image, key):
        colors, labels = self.cfg.colors, self.cfg.labels
        self._big(image, labels[key], 3, colors[key])
        self._clock(image, 22, colors["dim"])

    def _screen_free(self, image, snap, t):
        self._status(image, "free")

    def _screen_busy(self, image, snap, t):
        self._status(image, "busy")

    def _screen_on_air(self, image, snap, t):
        colors = self.cfg.colors
        red = colors["on_air"]
        pixels = image.load()
        width = self.size[0]
        for y in range(0, 18):                      # enseigne pleine, coins rognés
            for x in range(width):
                corner = (x in (0, width - 1)) and (y in (0, 17))
                if not corner:
                    pixels[x, y] = red
        self._big(image, self.cfg.labels["on_air"], 2, colors["white"])
        elapsed = _mmss(snap["on_air_elapsed"])
        text_x = (width - font.text_width(elapsed) - 6) // 2 + 6
        self._text(image, elapsed, 22, colors["dim"], x=text_x)
        if int(t * 2) % 2 == 0:                     # voyant d'enregistrement
            for dx in range(3):
                for dy in range(3):
                    pixels[text_x - 6 + dx, 24 + dy] = red

    def _countdown(self, image, snap, key, t):
        colors = self.cfg.colors
        timer = snap["timer"]
        color = colors[key]
        self._text(image, self.cfg.labels[key], 1, color)
        blink_off = (not timer["running"]) and int(t * 2) % 2 == 1
        if not blink_off:                           # clignote quand en pause
            self._big(image, _mmss(timer["remaining"]), 11, colors["white"])
        total = timer["total"] or 1.0
        self._bar(image, 1.0 - timer["remaining"] / total, color)

    def _screen_focus(self, image, snap, t):
        self._countdown(image, snap, "focus", t)

    def _screen_break(self, image, snap, t):
        self._countdown(image, snap, "break", t)

    def _screen_setting(self, image, snap, t):
        colors = self.cfg.colors
        self._text(image, self.cfg.labels["focus"], 1, colors["focus"])
        self._big(image, "%d MIN" % snap["timer"]["focus_minutes"], 11, colors["white"])

    def _screen_hey(self, image, snap, t):
        colors = self.cfg.colors
        label = self.cfg.labels["hey"]
        pulse = 0.65 + 0.35 * math.sin(t * 8.0)
        color = _scale(colors["hey"], pulse)
        message = snap["hey_text"]
        if not message:
            bounce = int(round(2 * math.sin(t * 6.0)))
            self._big(image, label, 5 + bounce, color, wanted=3)
            return
        self._big(image, label, 2, color)
        width = self.size[0]
        text_width = font.text_width(message)
        if text_width <= width:
            self._text(image, message, 21, colors["white"])
        else:                                       # défilement du message
            span = text_width + width
            offset = int(t * 24) % span
            self._text(image, message, 21, colors["white"], x=width - offset)

    def _screen_urgency(self, image, snap, t):
        colors = self.cfg.colors
        red = colors["urgency"]
        inverted = int(t * 4) % 2 == 0              # flash à 2 Hz
        if inverted:
            image.paste(red, (0, 0, self.size[0], self.size[1]))
        label = self.cfg.labels["urgency"]
        self._big(image, label, 9, colors["white"] if inverted else red)
