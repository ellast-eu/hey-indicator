"""Dessin de l'écran avant : un instantané d'état -> une image PIL.

La mise en page suit la hauteur de la dalle : texte principal en police
x2 sur 32 lignes, x3 à partir de 40 lignes.

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
        self.k = 3 if cfg.rows >= 40 else 2         # échelle du texte principal
        self.big_h = font.HEIGHT * self.k

    # --- primitives ---------------------------------------------------------------
    def _text(self, image, text, y, color, sx=1, sy=None, x=None, gap=None):
        sy = sx if sy is None else sy
        if x is None:
            x = (self.size[0] - font.text_width(text, sx, gap)) // 2
        font.draw_text(image.load(), x, y, text, color, sx, sy, gap, size=self.size)

    def _fit(self, text, wanted):
        """(échelle, espacement) : l'échelle `wanted` si le texte tient, sinon
        l'espacement resserré, sinon l'échelle inférieure."""
        for scale in range(wanted, 0, -1):
            # À x3 et plus, des lettres collées deviennent illisibles.
            for gap in ((scale, 1) if scale <= 2 else (scale,)):
                if font.text_width(text, scale, gap) <= self.size[0]:
                    return scale, gap
        return 1, 1

    def _big(self, image, text, y, color, wanted=None):
        """Texte principal ; renvoie l'échelle utilisée."""
        scale, gap = self._fit(text, wanted or self.k)
        self._text(image, text, y, color, sx=scale, gap=gap)
        return scale

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
        rows = self.size[1]
        gap = 5 if rows < 40 else 4
        top = (rows - self.big_h - gap - font.HEIGHT) // 2
        self._big(image, labels[key], top, colors[key])
        self._clock(image, top + self.big_h + gap, colors["dim"])

    def _screen_free(self, image, snap, t):
        self._status(image, "free")

    def _screen_busy(self, image, snap, t):
        self._status(image, "busy")

    def _screen_on_air(self, image, snap, t):
        colors = self.cfg.colors
        red = colors["on_air"]
        pixels = image.load()
        width, rows = self.size
        label = self.cfg.labels["on_air"]
        sign_h = font.HEIGHT * self._fit(label, self.k)[0] + 4
        for y in range(0, sign_h):                  # enseigne pleine, coins rognés
            for x in range(width):
                corner = (x in (0, width - 1)) and (y in (0, sign_h - 1))
                if not corner:
                    pixels[x, y] = red
        self._big(image, label, 2, colors["white"])
        elapsed = _mmss(snap["on_air_elapsed"])
        sx = 2 if rows - sign_h >= 2 * font.HEIGHT + 4 else 1   # chrono plus grand si la place le permet
        dot = 3 * sx
        text_h = font.HEIGHT * sx
        text_y = sign_h + (rows - sign_h - text_h + 1) // 2
        text_x = (width - font.text_width(elapsed, sx) - 2 * dot) // 2 + 2 * dot
        self._text(image, elapsed, text_y, colors["dim"], sx=sx, x=text_x)
        if int(t * 2) % 2 == 0:                     # voyant d'enregistrement
            top = text_y + (text_h - dot) // 2
            for dx in range(dot):
                for dy in range(dot):
                    pixels[text_x - 2 * dot + dx, top + dy] = red

    def _main_y(self, text):
        """Ligne du grand texte sous une étiquette (minuteur, réglage)."""
        height = font.HEIGHT * self._fit(text, self.k)[0]
        return 8 + (self.size[1] - 2 - 8 - height) // 2

    def _countdown(self, image, snap, key, t):
        colors = self.cfg.colors
        timer = snap["timer"]
        color = colors[key]
        self._text(image, self.cfg.labels[key], 1, color)
        blink_off = (not timer["running"]) and int(t * 2) % 2 == 1
        if not blink_off:                           # clignote quand en pause
            remaining = _mmss(timer["remaining"])
            self._big(image, remaining, self._main_y(remaining), colors["white"])
        total = timer["total"] or 1.0
        self._bar(image, 1.0 - timer["remaining"] / total, color)

    def _screen_focus(self, image, snap, t):
        self._countdown(image, snap, "focus", t)

    def _screen_break(self, image, snap, t):
        self._countdown(image, snap, "break", t)

    def _screen_setting(self, image, snap, t):
        colors = self.cfg.colors
        self._text(image, self.cfg.labels["focus"], 1, colors["focus"])
        text = "%d MIN" % snap["timer"]["focus_minutes"]
        self._big(image, text, self._main_y(text), colors["white"])

    def _screen_hey(self, image, snap, t):
        colors = self.cfg.colors
        label = self.cfg.labels["hey"]
        rows = self.size[1]
        pulse = 0.65 + 0.35 * math.sin(t * 8.0)
        color = _scale(colors["hey"], pulse)
        message = snap["hey_text"]
        if not message:
            scale, _ = self._fit(label, self.k + 1)
            bounce = int(round(2 * math.sin(t * 6.0)))
            self._big(image, label, (rows - font.HEIGHT * scale) // 2 + bounce, color,
                      wanted=self.k + 1)
            return
        self._big(image, label, 2, color)
        width = self.size[0]
        text_y = rows - 11
        text_width = font.text_width(message)
        if text_width <= width:
            self._text(image, message, text_y, colors["white"])
        else:                                       # défilement du message
            span = text_width + width
            offset = int(t * 24) % span
            self._text(image, message, text_y, colors["white"], x=width - offset)

    def _screen_urgency(self, image, snap, t):
        colors = self.cfg.colors
        red = colors["urgency"]
        inverted = int(t * 4) % 2 == 0              # flash à 2 Hz
        if inverted:
            image.paste(red, (0, 0, self.size[0], self.size[1]))
        label = self.cfg.labels["urgency"]
        scale, _ = self._fit(label, self.k)
        self._big(image, label, (self.size[1] - font.HEIGHT * scale) // 2,
                  colors["white"] if inverted else red)
