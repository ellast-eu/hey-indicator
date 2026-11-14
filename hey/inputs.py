"""Commandes : boutons, interrupteur, molette et buzzer réels (gpiozero),
ou clavier pour le simulateur."""

import sys
import threading
import time

# Petites mélodies : (fréquence en Hz, durée en s) ; 0 Hz = silence.
SOUNDS = {
    "hey": [(880, 0.10), (0, 0.05), (1175, 0.15)],
    "urgency": [(1568, 0.15), (0, 0.08)] * 4,
    "focus_end": [(784, 0.12), (988, 0.12), (1175, 0.25)],
    "break_end": [(1175, 0.12), (988, 0.12), (784, 0.25)],
}


class GpioInputs:
    """Câblage : chaque contact relie sa broche à la masse (pull-up interne).

    La v1 utilisait des pull-down et un retour au 3,3 V ; passer à la masse
    évite de promener du 3,3 V dans le boîtier.
    """

    def __init__(self, cfg, indicator):
        from gpiozero import Button, PWMOutputDevice, RotaryEncoder

        cfg.check_pins()
        self._indicator = indicator
        self._devices = []

        # Interrupteur Free/Busy : fermé = busy.
        switch = Button(cfg.switch_pin, pull_up=True, bounce_time=0.05)
        switch.when_pressed = lambda: indicator.set_mode("busy")
        switch.when_released = lambda: indicator.set_mode("free")
        indicator.set_mode("busy" if switch.is_pressed else "free")
        self._devices.append(switch)

        actions = {
            "on_air": indicator.set_on_air,     # bascule à chaque appui
            "hey": indicator.hey,
            "urgency": indicator.urgency,
        }
        for name, pin in cfg.button_pins.items():
            button = Button(pin, pull_up=True, bounce_time=0.05)
            button.when_pressed = actions[name]
            self._devices.append(button)

        # Molette : rotation = minutes.
        encoder = RotaryEncoder(cfg.encoder_a_pin, cfg.encoder_b_pin, max_steps=0)
        encoder.when_rotated_clockwise = lambda: indicator.adjust(+1)
        encoder.when_rotated_counter_clockwise = lambda: indicator.adjust(-1)
        self._devices.append(encoder)

        # Touche mécanique du dessus et appui sur la molette, même rôle :
        # appui court = acquitte une alerte, sinon démarre / met en pause ;
        # appui long = remise à zéro du minuteur.
        for pin in (cfg.key_pin, cfg.encoder_sw_pin):
            if pin is not None:
                self._devices.append(self._press_button(Button, pin, cfg.hold_time))

        self._buzzer = None
        self._closing = False
        self._sound_lock = threading.Lock()
        if cfg.buzzer_pin is not None:
            self._buzzer = PWMOutputDevice(cfg.buzzer_pin, initial_value=0, frequency=880)
            self._devices.append(self._buzzer)
            indicator.subscribe(self._on_event)

    def _press_button(self, button_class, pin, hold_time):
        """Bouton à appui court / appui long, chacun avec son propre état."""
        button = button_class(pin, pull_up=True, bounce_time=0.05, hold_time=hold_time)
        state = {"held": False}

        def on_hold():
            state["held"] = True
            self._indicator.long_press()

        def on_release():
            if not state["held"]:
                self._indicator.press()
            state["held"] = False

        button.when_held = on_hold
        button.when_released = on_release
        return button

    def _on_event(self, name):
        if name in SOUNDS:
            threading.Thread(target=self._play, args=(SOUNDS[name],), daemon=True).start()

    def _play(self, notes):
        with self._sound_lock:
            for frequency, duration in notes:
                if self._closing:
                    return
                if frequency:
                    self._buzzer.frequency = frequency
                    self._buzzer.value = 0.5
                else:
                    self._buzzer.value = 0
                time.sleep(duration)
            self._buzzer.value = 0

    def close(self):
        self._closing = True
        with self._sound_lock:              # attend la fin de la note en cours
            for device in self._devices:
                device.close()


KEYS_HELP = ("f/b free/busy   o on air   h hey   u urgency   espace touche   "
             "r reset   +/- minutes   q quitter")


class KeyboardInputs:
    """Clavier du simulateur. Sans terminal interactif, ne fait rien."""

    def __init__(self, cfg, indicator, on_quit):
        self._indicator = indicator
        self._on_quit = on_quit
        self._saved = None
        if not sys.stdin.isatty():
            return
        import termios
        import tty

        self._fd = sys.stdin.fileno()
        self._saved = termios.tcgetattr(self._fd)
        tty.setcbreak(self._fd)
        threading.Thread(target=self._loop, daemon=True).start()

    def _loop(self):
        ind = self._indicator
        actions = {
            "f": lambda: ind.set_mode("free"),
            "b": lambda: ind.set_mode("busy"),
            "o": ind.set_on_air,
            "h": ind.hey,
            "u": ind.urgency,
            " ": ind.press,
            "r": ind.long_press,
            "+": lambda: ind.adjust(+1),
            "=": lambda: ind.adjust(+1),
            "-": lambda: ind.adjust(-1),
            "q": self._on_quit,
        }
        while True:
            key = sys.stdin.read(1)
            if not key:
                return
            action = actions.get(key.lower())
            if action:
                action()

    def close(self):
        if self._saved is not None:
            import termios

            termios.tcsetattr(self._fd, termios.TCSADRAIN, self._saved)
