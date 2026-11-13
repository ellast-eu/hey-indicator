"""Configuration : tout ce qui se règle est ici.

Les numéros de broches sont en notation BCM, comme dans la v1.
Les broches ont changé par rapport à la v1 : le RGB Matrix Bonnet occupe
4, 5, 6, 12, 13, 16, 17, 20, 21, 22, 23, 26 et 27 (plus 18 si le pont
« qualité » GPIO4-GPIO18 est soudé). Il reste 7, 8, 9, 10, 11, 19, 24, 25,
ainsi que l'I2C (2, 3) et l'UART (14, 15) gardés libres pour plus tard.
"""

import os
from dataclasses import dataclass, field


@dataclass
class Config:
    # --- Écran : dalle HUB75 64x32 au pas de 2,5 mm (160 x 80 mm) -----------
    cols: int = 64
    rows: int = 32
    # "adafruit-hat" : bonnet tel quel. "adafruit-hat-pwm" : pont GPIO4-GPIO18
    # soudé (image plus stable, mais le son embarqué du Pi doit être coupé).
    hardware_mapping: str = "adafruit-hat"
    gpio_slowdown: int = 2          # Pi Zero 2 W : 1 ou 2 ; Pi 4 : 4
    brightness: int = 60            # 1..100
    fps: int = 20

    # --- Commandes (boutons câblés entre la broche et la masse) -------------
    switch_pin: int = 19            # interrupteur Free/Busy (inchangé)
    button_pins: dict = field(default_factory=lambda: {
        "on_air": 25,
        "hey": 24,
        "urgency": 8,
    })
    encoder_a_pin: int = 9
    encoder_b_pin: int = 10
    encoder_sw_pin: int = 11
    buzzer_pin: int = 7             # buzzer passif ; None pour désactiver
    hold_time: float = 1.0          # appui long sur la molette (s)

    # --- Comportement --------------------------------------------------------
    focus_minutes: int = 25         # Pomodoro : travail
    break_minutes: int = 5          # Pomodoro : pause
    auto_cycle: bool = False        # True : relance un focus après la pause
    hey_seconds: float = 10.0       # durée d'affichage d'un « Hey! »
    urgent_timeout: float = 120.0   # arrêt auto de l'alerte (0 = jamais)
    setting_seconds: float = 2.5    # durée d'affichage du réglage du minuteur
    message_max: int = 60           # longueur max d'un message reçu par l'API

    # --- Textes et couleurs --------------------------------------------------
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

    # --- API HTTP locale -----------------------------------------------------
    http_host: str = "0.0.0.0"
    http_port: int = 8080
    # Jeton exigé pour toute requête POST s'il est défini (variable
    # d'environnement HEY_TOKEN). Sans jeton, n'importe qui sur le réseau
    # local peut piloter l'indicateur.
    token: str = field(default_factory=lambda: os.environ.get("HEY_TOKEN", ""))
