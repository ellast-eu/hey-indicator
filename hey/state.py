"""Machine à états de l'indicateur, indépendante du matériel.

Les cinq états de la v1 sont conservés (free, busy, on_air, hey, urgency) ;
s'y ajoute un minuteur Pomodoro. Tout passe par cette classe, que la commande
vienne d'un bouton, de la molette ou de l'API HTTP.

Priorité d'affichage : urgency > hey > réglage > on_air > minuteur > free/busy.
"""

import threading
import time
import unicodedata


def clean_text(text, limit):
    """Ramène un message libre au jeu de caractères de l'écran."""
    text = unicodedata.normalize("NFKD", str(text or ""))
    text = "".join(c for c in text if not unicodedata.combining(c))
    text = "".join(c if 32 <= ord(c) < 127 else " " for c in text)
    return " ".join(text.upper().split())[:limit]


class Indicator:
    def __init__(self, cfg, clock=time.monotonic):
        self.cfg = cfg
        self._clock = clock
        self._lock = threading.RLock()
        self._listeners = []

        self.mode = "free"              # "free" | "busy"
        self.on_air = False
        self._on_air_since = None
        self._hey_until = 0.0
        self.hey_text = ""
        self._urgent_since = None
        self._setting_until = 0.0

        self.focus_minutes = cfg.focus_minutes
        self.break_minutes = cfg.break_minutes
        self.phase = "idle"             # "idle" | "focus" | "break"
        self.running = False
        self._remaining = 0.0           # secondes restantes quand en pause
        self._deadline = 0.0            # échéance quand le minuteur tourne
        self._total = 0.0

    # --- évènements (sons, journal) ------------------------------------------
    def subscribe(self, callback):
        self._listeners.append(callback)

    def _emit(self, name):
        for callback in self._listeners:
            try:
                callback(name)
            except Exception:           # un son raté ne doit rien bloquer
                pass

    # --- états de la v1 ---------------------------------------------------------
    def set_mode(self, mode):
        if mode not in ("free", "busy"):
            raise ValueError("mode attendu : free ou busy")
        with self._lock:
            self.mode = mode

    def toggle_mode(self):
        with self._lock:
            self.mode = "busy" if self.mode == "free" else "free"

    def set_on_air(self, on=None):
        """on=None bascule l'état."""
        with self._lock:
            on = (not self.on_air) if on is None else bool(on)
            if on and not self.on_air:
                self._on_air_since = self._clock()
            self.on_air = on

    def hey(self, text=""):
        with self._lock:
            self.hey_text = clean_text(text, self.cfg.message_max)
            self._hey_until = self._clock() + self.cfg.hey_seconds
        self._emit("hey")

    def urgency(self):
        with self._lock:
            self._urgent_since = self._clock()
        self._emit("urgency")

    def acknowledge(self):
        """Acquitte l'alerte en cours. Renvoie True s'il y en avait une."""
        with self._lock:
            had = self._urgent_active() or self._hey_active()
            self._urgent_since = None
            self._hey_until = 0.0
            return had

    def _hey_active(self):
        return self._clock() < self._hey_until

    def _urgent_active(self):
        return self._urgent_since is not None

    # --- minuteur Pomodoro ------------------------------------------------------
    def timer_remaining(self):
        with self._lock:
            if self.phase == "idle":
                return self.focus_minutes * 60.0
            if self.running:
                return max(0.0, self._deadline - self._clock())
            return self._remaining

    def _start_phase(self, phase):
        minutes = self.focus_minutes if phase == "focus" else self.break_minutes
        self.phase = phase
        self.running = True
        self._total = minutes * 60.0
        self._deadline = self._clock() + self._total

    def timer_start(self, minutes=None):
        with self._lock:
            if minutes is not None:
                self.focus_minutes = max(1, min(180, int(minutes)))
            if self.phase == "idle":
                self._start_phase("focus")
            elif not self.running:
                self._deadline = self._clock() + self._remaining
                self.running = True

    def timer_pause(self):
        with self._lock:
            if self.phase != "idle" and self.running:
                self._remaining = max(0.0, self._deadline - self._clock())
                self.running = False

    def timer_toggle(self):
        with self._lock:
            if self.phase != "idle" and self.running:
                self.timer_pause()
            else:
                self.timer_start()

    def timer_reset(self):
        with self._lock:
            self.phase = "idle"
            self.running = False

    def adjust(self, steps):
        """Molette : règle la durée du focus, ou décale un minuteur en cours."""
        with self._lock:
            if self.phase == "idle":
                self.focus_minutes = max(1, min(180, self.focus_minutes + steps))
                self._setting_until = self._clock() + self.cfg.setting_seconds
            else:
                left = max(60.0, self.timer_remaining() + 60.0 * steps)
                self._total = max(self._total, left)
                if self.running:
                    self._deadline = self._clock() + left
                else:
                    self._remaining = left

    # --- commandes physiques ----------------------------------------------------
    def press(self):
        """Appui court sur la molette : acquitte une alerte, sinon start/pause."""
        if not self.acknowledge():
            self.timer_toggle()

    def long_press(self):
        self.timer_reset()

    # --- horloge ----------------------------------------------------------------
    def tick(self):
        """À appeler régulièrement : fait avancer minuteur et alertes."""
        event = None
        with self._lock:
            now = self._clock()
            if self.phase != "idle" and self.running and now >= self._deadline:
                if self.phase == "focus":
                    event = "focus_end"
                    self._start_phase("break")
                else:
                    event = "break_end"
                    if self.cfg.auto_cycle:
                        self._start_phase("focus")
                    else:
                        self.phase = "idle"
                        self.running = False
            timeout = self.cfg.urgent_timeout
            if self._urgent_active() and timeout and now - self._urgent_since > timeout:
                self._urgent_since = None
        if event:
            self._emit(event)

    # --- instantané pour l'écran et l'API ---------------------------------------
    def snapshot(self):
        with self._lock:
            now = self._clock()
            if self._urgent_active():
                screen = "urgency"
            elif self._hey_active():
                screen = "hey"
            elif now < self._setting_until:
                screen = "setting"
            elif self.on_air:
                screen = "on_air"
            elif self.phase != "idle":
                screen = self.phase
            else:
                screen = self.mode
            remaining = self.timer_remaining()
            total = self._total if self.phase != "idle" else self.focus_minutes * 60.0
            return {
                "screen": screen,
                "mode": self.mode,
                "on_air": self.on_air,
                "on_air_elapsed": (now - self._on_air_since) if self.on_air else 0.0,
                "hey": self._hey_active(),
                "hey_text": self.hey_text if self._hey_active() else "",
                "urgency": self._urgent_active(),
                "timer": {
                    "phase": self.phase,
                    "running": self.running,
                    "remaining": round(remaining, 1),
                    "total": total,
                    "focus_minutes": self.focus_minutes,
                    "break_minutes": self.break_minutes,
                },
            }
