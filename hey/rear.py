"""Écran arrière : OLED monochrome 128x64, tourné vers la personne au bureau.

L'avant dit aux autres si on est disponible ; l'arrière sert à celle qui
travaille : minuteur détaillé, message « Hey » en entier, ce que fait la
touche, adresse de l'API.
"""

import math
import socket
import time

from PIL import Image

from . import font

SIZE = (128, 64)
ON, OFF = 255, 0


def _mmss(seconds):
    seconds = int(math.ceil(seconds))
    return "%02d:%02d" % (seconds // 60, seconds % 60)


def local_address():
    """Adresse IP locale (aucun paquet n'est envoyé)."""
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("192.0.2.1", 9))         # adresse de documentation
        return probe.getsockname()[0]
    except OSError:
        return ""
    finally:
        probe.close()


def wrap(text, width, sx=1):
    """Coupe `text` en lignes de `width` pixels au plus, entre les mots."""
    lines, current = [], ""
    for word in text.split():
        candidate = (current + " " + word).strip()
        if font.text_width(candidate, sx) <= width:
            current = candidate
            continue
        if current:
            lines.append(current)
        while font.text_width(word, sx) > width:  # mot plus long qu'une ligne
            cut = len(word)
            while cut > 1 and font.text_width(word[:cut], sx) > width:
                cut -= 1
            lines.append(word[:cut])
            word = word[cut:]
        current = word
    if current:
        lines.append(current)
    return lines


class RearRenderer:
    def __init__(self, cfg, address=""):
        self.cfg = cfg
        self.address = address

    # --- primitives ---------------------------------------------------------------
    def _text(self, image, text, y, sx=1, x=None, color=ON, gap=None):
        if x is None:
            x = (SIZE[0] - font.text_width(text, sx, gap)) // 2
        font.draw_text(image.load(), x, y, text, color, sx, sx, gap, size=SIZE)

    def _fill(self, image, box, color=ON):
        image.paste(color, box)

    def _header(self, image, snap):
        """Bandeau inversé : état à gauche, heure à droite."""
        self._fill(image, (0, 0, SIZE[0], 10))
        mode = self.cfg.labels[snap["mode"]]
        flags = [mode]
        if snap["on_air"]:
            flags.append(self.cfg.labels["on_air"])
        self._text(image, "  ".join(flags), 2, x=3, color=OFF)
        clock = time.strftime("%H:%M")
        self._text(image, clock, 2, x=SIZE[0] - 3 - font.text_width(clock), color=OFF)

    def _footer(self, image, text):
        self._text(image, text, SIZE[1] - 8)

    def _progress(self, image, fraction, y=44):
        left, right = 8, SIZE[0] - 8
        pixels = image.load()
        for x in range(left, right):
            pixels[x, y] = pixels[x, y + 5] = ON
        for yy in range(y, y + 6):
            pixels[left, yy] = pixels[right - 1, yy] = ON
        lit = int((right - left - 4) * max(0.0, min(1.0, fraction)))
        self._fill(image, (left + 2, y + 2, left + 2 + lit, y + 4))

    # --- écrans -------------------------------------------------------------------
    def render(self, snap, t=None):
        t = time.monotonic() if t is None else t
        image = Image.new("L", SIZE, OFF)
        screen = snap["screen"]
        if screen == "urgency":
            self._urgency(image, t)
        else:
            self._header(image, snap)
            getattr(self, "_" + screen, self._idle)(image, snap, t)
        return image.convert("1")

    def _idle(self, image, snap, t):
        minutes = snap["timer"]["focus_minutes"]
        self._text(image, self.cfg.labels["focus"], 16)
        self._text(image, "%d MIN" % minutes, 26, sx=2)
        address = ("%s:%d" % (self.address, self.cfg.http_port)) if self.address else ""
        # Alterne l'aide de la touche et l'adresse de l'API toutes les 4 s.
        if address and int(t / 4) % 2:
            self._footer(image, address)
        else:
            self._footer(image, "TOUCHE : DEMARRER")

    _free = _busy = _idle

    def _setting(self, image, snap, t):
        self._text(image, "DUREE DU FOCUS", 16)
        self._text(image, "%d MIN" % snap["timer"]["focus_minutes"], 27, sx=3, gap=2)
        self._footer(image, "MOLETTE : +/- 1 MIN")

    def _countdown(self, image, snap, t):
        timer = snap["timer"]
        label = self.cfg.labels[timer["phase"]]
        if not timer["running"]:
            label += " (PAUSE)"
        self._text(image, label, 14)
        self._text(image, _mmss(timer["remaining"]), 23, sx=3)
        total = timer["total"] or 1.0
        self._progress(image, 1.0 - timer["remaining"] / total, y=46)
        hint = "TOUCHE : REPRENDRE" if not timer["running"] else "TOUCHE : PAUSE"
        self._footer(image, hint)

    _focus = _break = _countdown

    def _on_air(self, image, snap, t):
        self._text(image, self.cfg.labels["on_air"], 16, sx=2)
        self._text(image, _mmss(snap["on_air_elapsed"]), 34, sx=2)
        self._footer(image, "BOUTON ON AIR : FIN")

    def _hey(self, image, snap, t):
        message = snap["hey_text"]
        if not message:
            self._text(image, self.cfg.labels["hey"], 18, sx=3)
            self._footer(image, "TOUCHE : VU")
            return
        self._text(image, self.cfg.labels["hey"], 14, sx=1)
        lines = wrap(message, SIZE[0] - 4)[:4]
        for index, line in enumerate(lines):
            self._text(image, line, 24 + index * 9)
        if len(lines) < 4:
            self._footer(image, "TOUCHE : VU")

    def _urgency(self, image, t):
        inverted = int(t * 4) % 2 == 0
        if inverted:
            self._fill(image, (0, 0) + SIZE)
        color = OFF if inverted else ON
        self._text(image, self.cfg.labels["urgency"], 14, sx=3, gap=2, color=color)
        self._text(image, "TOUCHE : ACQUITTER", 48, color=color)
