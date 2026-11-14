"""Configuration : tout ce qui se règle est ici.

Les numéros de broches sont en notation BCM, comme dans la v1.

Le RGB Matrix Bonnet occupe 4, 5, 6, 12, 13, 16, 17, 20, 21, 22, 23, 26, 27,
plus 24 (ligne d'adresse E) pour les dalles de plus de 32 lignes, et 18 si le
pont « qualité » GPIO4-GPIO18 est soudé. L'écran arrière prend l'I2C (2, 3).
"""

import os
from dataclasses import dataclass, field

# Dalles connues. Le pas (mm) ne sert qu'aux aperçus et au boîtier.
PANELS = {
    # Dalle HUB75 64x32 au pas de 2,5 mm, balayage 1/16 : 160 x 80 mm.
    "64x32": {"cols": 64, "rows": 32, "pitch": 2.5},
    # Waveshare RGB-Matrix-P4-80x40, balayage 1/20 : 320 x 160 mm, 1 kg.
    "80x40": {"cols": 80, "rows": 40, "pitch": 4.0},
}

BONNET_PINS = {4, 5, 6, 12, 13, 16, 17, 20, 21, 22, 23, 26, 27}
I2C_PINS = {2, 3}


@dataclass
class Config:
    # --- Écran avant : dalle HUB75 ----------------------------------------------
    # Choix de la dalle : variable d'environnement HEY_PANEL ou --panel.
    panel: str = field(default_factory=lambda: os.environ.get("HEY_PANEL", "64x32"))
    cols: int = 0                   # 0 : pris dans PANELS
    rows: int = 0
    pitch: float = 0.0
    # "adafruit-hat" : bonnet tel quel. "adafruit-hat-pwm" : pont GPIO4-GPIO18
    # soudé (image plus stable, mais le son embarqué du Pi doit être coupé).
    hardware_mapping: str = "adafruit-hat"
    gpio_slowdown: int = 2          # Pi Zero 2 W : 1 ou 2 ; Pi 4 : 4
    brightness: int = 60            # 1..100
    fps: int = 20

    # --- Écran arrière : OLED monochrome 128x64 en I2C (SH1106 1,3") ----------
    rear_enabled: bool = True
    rear_driver: str = "sh1106"     # "ssd1306" (0,96"), "ssd1309" (2,42")
    rear_address: int = 0x3C
    rear_contrast: int = 128        # 0..255
    rear_rotate: int = 0            # 0..3 : quarts de tour selon le montage
    rear_fps: float = 4.0           # l'I2C est lent : inutile de rafraîchir plus

    # --- Commandes (contacts câblés entre la broche et la masse) ---------------
    switch_pin: int = 19            # interrupteur Free/Busy (inchangé depuis la v1)
    key_pin: int = 15               # touche mécanique du dessus
    button_pins: dict = field(default_factory=lambda: {
        "on_air": 25,
        "hey": 18,
        "urgency": 8,
    })
    encoder_a_pin: int = 9
    encoder_b_pin: int = 10
    encoder_sw_pin: int = 11
    buzzer_pin: int = 7             # buzzer passif ; None pour désactiver
    hold_time: float = 1.0          # appui long sur la touche ou la molette (s)

    # --- Comportement ----------------------------------------------------------
    focus_minutes: int = 25         # Pomodoro : travail
    break_minutes: int = 5          # Pomodoro : pause
    auto_cycle: bool = False        # True : relance un focus après la pause
    hey_seconds: float = 10.0       # durée d'affichage d'un « Hey! »
    urgent_timeout: float = 120.0   # arrêt auto de l'alerte (0 = jamais)
    setting_seconds: float = 2.5    # durée d'affichage du réglage du minuteur
    message_max: int = 60           # longueur max d'un message reçu par l'API

    # --- Textes et couleurs ----------------------------------------------------
    labels: dict = field(default_factory=lambda: {
        "free": "FREE",
        "busy": "BUSY",
        "on_air": "ON AIR",
        "hey": "HEY!",
        "urgency": "URGENT",
        "focus": "FOCUS",
        "break": "BREAK",
    })
    colors: dict = field(default_factory=lambda: {
        "free": (0, 220, 70),
        "busy": (255, 40, 30),
        "on_air": (255, 0, 0),
        "hey": (255, 200, 0),
        "urgency": (255, 0, 0),
        "focus": (255, 90, 20),
        "break": (40, 140, 255),
        "dim": (110, 110, 110),
        "white": (255, 255, 255),
    })

    # --- API HTTP locale -------------------------------------------------------
    http_host: str = "0.0.0.0"
    http_port: int = 8080
    # Jeton exigé pour toute requête POST s'il est défini (variable
    # d'environnement HEY_TOKEN). Sans jeton, n'importe qui sur le réseau
    # local peut piloter l'indicateur.
    token: str = field(default_factory=lambda: os.environ.get("HEY_TOKEN", ""))

    def __post_init__(self):
        if self.panel not in PANELS:
            raise ValueError("dalle inconnue : %s (connues : %s)"
                             % (self.panel, ", ".join(PANELS)))
        preset = PANELS[self.panel]
        self.cols = self.cols or preset["cols"]
        self.rows = self.rows or preset["rows"]
        self.pitch = self.pitch or preset["pitch"]

    # --- Contrôle du brochage ---------------------------------------------------
    def reserved_pins(self):
        """Broches prises par le bonnet et l'écran arrière."""
        pins = set(BONNET_PINS)
        if self.rows > 32:
            pins.add(24)                # ligne d'adresse E
        if self.hardware_mapping.endswith("-pwm"):
            pins.add(18)
        if self.rear_enabled:
            pins |= I2C_PINS
        return pins

    def input_pins(self):
        pins = {"switch": self.switch_pin, "key": self.key_pin,
                "encoder_a": self.encoder_a_pin, "encoder_b": self.encoder_b_pin,
                "encoder_sw": self.encoder_sw_pin}
        pins.update(self.button_pins)
        if self.buzzer_pin is not None:
            pins["buzzer"] = self.buzzer_pin
        return pins

    def check_pins(self):
        """Lève ValueError si deux fonctions partagent une broche."""
        used = {}
        reserved = self.reserved_pins()
        for name, pin in self.input_pins().items():
            if pin is None:
                continue
            if pin in reserved:
                raise ValueError("GPIO %d (%s) est déjà pris par la dalle ou l'écran arrière"
                                 % (pin, name))
            if pin in used:
                raise ValueError("GPIO %d utilisé deux fois : %s et %s" % (pin, used[pin], name))
            used[pin] = name
