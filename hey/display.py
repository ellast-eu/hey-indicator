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


class OledDisplay:
    """Écran arrière OLED 128x64 en I2C, via luma.oled.

    N'envoie une image que si elle a changé : à 100 kHz, une image complète
    occupe le bus près de 0,1 s (voir hardware/README.md pour passer à 400 kHz).
    """

    def __init__(self, cfg):
        from luma.core.interface.serial import i2c
        from luma.oled import device

        driver = getattr(device, cfg.rear_driver)   # sh1106, ssd1306, ssd1309...
        self._device = driver(i2c(port=1, address=cfg.rear_address), rotate=cfg.rear_rotate)
        self._device.contrast(cfg.rear_contrast)
        self._last = None

    def show(self, image):
        data = image.tobytes()
        if data != self._last:
            self._device.display(image)
            self._last = data

    def close(self):
        self._device.clear()


class TerminalDisplay:
    """Simulateur : chaque caractère « ▀ » porte deux pixels superposés."""

    def __init__(self, cfg, stream=None):
        self._stream = stream or sys.stdout
        self._first = True
        self.brightness = cfg.brightness

    def show(self, image, rear=None):
        """Dessine l'avant, puis l'arrière si le terminal est assez grand."""
        out = ["\x1b[H" if not self._first else "\x1b[2J\x1b[H\x1b[?25l"]
        self._first = False
        out += self._blocks(image.convert("RGB"))
        if rear is not None:
            import shutil

            columns, lines = shutil.get_terminal_size()
            if columns >= rear.size[0] and lines >= (image.size[1] + rear.size[1]) // 2 + 6:
                out.append("\x1b[0mArrière :\x1b[K\r\n")
                out += self._blocks(rear.convert("RGB"), tint=(120, 200, 255))
        self._stream.write("".join(out))
        self._stream.flush()

    @staticmethod
    def _blocks(image, tint=None):
        width, height = image.size
        pixels = image.load()
        rows = []
        for y in range(0, height, 2):
            line = []
            for x in range(width):
                top = pixels[x, y]
                bottom = pixels[x, y + 1] if y + 1 < height else (0, 0, 0)
                if tint:                        # OLED monochrome : teinte bleutée
                    top = tint if top[0] else (0, 0, 0)
                    bottom = tint if bottom[0] else (0, 0, 0)
                line.append("\x1b[38;2;%d;%d;%dm\x1b[48;2;%d;%d;%dm▀" % (top + bottom))
            rows.append("".join(line) + "\x1b[0m\r\n")
        return rows

    def set_brightness(self, value):
        self.brightness = max(1, min(100, int(value)))

    def close(self):
        self._stream.write("\x1b[0m\x1b[?25h\r\n")
        self._stream.flush()


def save_png(image, path, zoom=10, gap=2, tint=None):
    """Enregistre l'image agrandie, chaque LED en pastille (pour la doc).

    `tint` : couleur des pixels allumés d'un écran monochrome."""
    from PIL import Image, ImageDraw

    image = image.convert("RGB")
    width, height = image.size
    big = Image.new("RGB", (width * zoom, height * zoom), (12, 12, 14))
    draw = ImageDraw.Draw(big)
    pixels = image.load()
    for y in range(height):
        for x in range(width):
            color = pixels[x, y]
            if tint and color != (0, 0, 0):
                color = tint
            if color == (0, 0, 0):
                color = (26, 26, 30)
            draw.ellipse((x * zoom + gap // 2, y * zoom + gap // 2,
                          (x + 1) * zoom - gap // 2 - 1, (y + 1) * zoom - gap // 2 - 1),
                         fill=color)
    big.save(path)
