"""Sorties d'affichage : la dalle HUB75 réelle, ou un simulateur dans le terminal."""

import sys


class Hub75Display:
    """Dalle HUB75 pilotée par rpi-rgb-led-matrix (hzeller) via le RGB Matrix Bonnet.

    Le programme doit tourner en root. On garde les privilèges après
    l'initialisation (drop_privileges=False), sinon la bibliothèque bascule sur
    l'utilisateur « daemon » et gpiozero perd l'accès aux boutons.
    """

    def __init__(self, cfg):
        from rgbmatrix import RGBMatrix, RGBMatrixOptions

        options = RGBMatrixOptions()
        options.rows = cfg.rows
        options.cols = cfg.cols
        options.chain_length = 1
        options.parallel = 1
        options.hardware_mapping = cfg.hardware_mapping
        options.gpio_slowdown = cfg.gpio_slowdown
        options.brightness = cfg.brightness
        options.drop_privileges = False
        self._matrix = RGBMatrix(options=options)
        self._canvas = self._matrix.CreateFrameCanvas()

    def show(self, image):
        self._canvas.SetImage(image)
        self._canvas = self._matrix.SwapOnVSync(self._canvas)

    def set_brightness(self, value):
        self._matrix.brightness = max(1, min(100, int(value)))

    def close(self):
        self._matrix.Clear()


class TerminalDisplay:
    """Simulateur : chaque caractère « ▀ » porte deux pixels superposés."""

    def __init__(self, cfg, stream=None):
        self._stream = stream or sys.stdout
        self._first = True
        self.brightness = cfg.brightness

    def show(self, image):
        width, height = image.size
        pixels = image.load()
        out = ["\x1b[H" if not self._first else "\x1b[2J\x1b[H\x1b[?25l"]
        self._first = False
        for y in range(0, height, 2):
            line = []
            for x in range(width):
                top = pixels[x, y]
                bottom = pixels[x, y + 1] if y + 1 < height else (0, 0, 0)
                line.append("\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm▀" % (top + bottom))
            out.append("".join(line) + "\x1b[0m\r\n")
        self._stream.write("".join(out))
        self._stream.flush()

    def set_brightness(self, value):
        self.brightness = max(1, min(100, int(value)))

    def close(self):
        self._stream.write("\x1b[0m\x1b[?25h\r\n")
        self._stream.flush()


def save_png(image, path, zoom=10, gap=2):
    """Enregistre l'image agrandie, chaque LED en pastille (pour la doc)."""
    from PIL import Image, ImageDraw

    width, height = image.size
    big = Image.new("RGB", (width * zoom, height * zoom), (12, 12, 14))
    draw = ImageDraw.Draw(big)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            color = pixels[x, y]
            if color == (0, 0, 0):
                color = (26, 26, 30)
            draw.ellipse((x * zoom + gap // 2, y * zoom + gap // 2,
                          (x + 1) * zoom - gap // 2 - 1, (y + 1) * zoom - gap // 2 - 1),
                         fill=color)
    big.save(path)
