"""Tests sans matériel :  python3 -m unittest discover -s tests -v"""

import json
import os
import sys
import unittest
import urllib.error
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from hey import font
from hey.api import start_server
from hey.config import Config
from hey.rear import RearRenderer, wrap
from hey.render import Renderer
from hey.state import Indicator, clean_text


class FakeClock:
    def __init__(self):
        self.now = 500.0

    def __call__(self):
        return self.now


class StateTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.clock = FakeClock()
        self.ind = Indicator(self.cfg, self.clock)
        self.events = []
        self.ind.subscribe(self.events.append)

    def screen(self):
        return self.ind.snapshot()["screen"]

    def test_free_busy(self):
        self.assertEqual(self.screen(), "free")
        self.ind.set_mode("busy")
        self.assertEqual(self.screen(), "busy")
        with self.assertRaises(ValueError):
            self.ind.set_mode("dnd")

    def test_priorities(self):
        self.ind.set_mode("busy")
        self.ind.timer_start()
        self.assertEqual(self.screen(), "focus")
        self.ind.set_on_air(True)
        self.assertEqual(self.screen(), "on_air")
        self.ind.hey()
        self.assertEqual(self.screen(), "hey")
        self.ind.urgency()
        self.assertEqual(self.screen(), "urgency")
        self.assertTrue(self.ind.acknowledge())
        self.assertEqual(self.screen(), "on_air")
        self.ind.set_on_air()
        self.assertEqual(self.screen(), "focus")
        self.assertEqual(self.events, ["hey", "urgency"])

    def test_hey_expires(self):
        self.ind.hey("coucou")
        self.assertEqual(self.ind.snapshot()["hey_text"], "COUCOU")
        self.clock.now += self.cfg.hey_seconds + 0.1
        self.assertEqual(self.screen(), "free")

    def test_urgency_timeout(self):
        self.ind.urgency()
        self.clock.now += self.cfg.urgent_timeout + 1
        self.ind.tick()
        self.assertEqual(self.screen(), "free")

    def test_pomodoro_cycle(self):
        self.ind.timer_start()
        self.clock.now += 10 * 60
        self.ind.tick()
        self.assertAlmostEqual(self.ind.timer_remaining(), 15 * 60)
        self.ind.timer_pause()
        self.clock.now += 3600                      # la pause ne décompte pas
        self.assertAlmostEqual(self.ind.timer_remaining(), 15 * 60)
        self.ind.timer_toggle()
        self.clock.now += 15 * 60
        self.ind.tick()
        self.assertEqual(self.screen(), "break")
        self.assertAlmostEqual(self.ind.timer_remaining(), 5 * 60)
        self.clock.now += 5 * 60
        self.ind.tick()
        self.assertEqual(self.screen(), "free")
        self.assertEqual(self.events, ["focus_end", "break_end"])

    def test_knob(self):
        self.ind.adjust(+5)
        self.assertEqual(self.screen(), "setting")
        self.assertEqual(self.ind.focus_minutes, 30)
        self.ind.adjust(-100)
        self.assertEqual(self.ind.focus_minutes, 1)
        self.ind.press()                            # démarre
        self.assertTrue(self.ind.running)
        self.ind.adjust(+2)                         # décale le minuteur en cours
        self.assertAlmostEqual(self.ind.timer_remaining(), 3 * 60)
        self.ind.urgency()
        self.ind.press()                            # acquitte sans toucher au minuteur
        self.assertTrue(self.ind.running)
        self.ind.long_press()
        self.assertEqual(self.ind.phase, "idle")

    def test_clean_text(self):
        self.assertEqual(clean_text("  Réunion\n à 14h 🎉 ", 60), "REUNION A 14H")
        self.assertEqual(len(clean_text("x" * 200, 60)), 60)


class ConfigTest(unittest.TestCase):
    def test_default_pins_are_free(self):
        Config().check_pins()

    def test_pin_conflicts_are_caught(self):
        cfg = Config(hardware_mapping="adafruit-hat-pwm")
        cfg.button_pins["hey"] = 18                 # GPIO 18 pris par le pont qualité
        with self.assertRaises(ValueError):
            cfg.check_pins()
        cfg = Config(rows=64)                       # dalle 64 lignes : GPIO 24 = ligne E
        with self.assertRaises(ValueError):
            cfg.check_pins()
        cfg = Config()
        cfg.key_pin = cfg.switch_pin
        with self.assertRaises(ValueError):
            cfg.check_pins()
        cfg = Config()
        cfg.key_pin = 3                             # I2C de l'écran arrière
        with self.assertRaises(ValueError):
            cfg.check_pins()


class RenderTest(unittest.TestCase):
    def test_every_screen_draws_and_fits(self):
        cfg = Config()
        size = (64, 32)
        clock = FakeClock()
        renderer = Renderer(cfg)
        rear = RearRenderer(cfg, "10.0.0.2")
        ind = Indicator(cfg, clock)
        steps = [lambda: None, lambda: ind.set_mode("busy"), lambda: ind.adjust(1),
                 lambda: (setattr(clock, "now", clock.now + 5), ind.timer_start()),
                 lambda: ind.set_on_air(True), lambda: ind.hey("un message bien trop long pour tenir"),
                 ind.urgency]
        seen = set()
        for step in steps:
            step()
            snap = ind.snapshot()
            seen.add(snap["screen"])
            for t in (0.0, 0.3, 1.7, 5.0):
                image = renderer.render(snap, t)
                self.assertEqual(image.size, size)
                self.assertIsNotNone(image.getbbox(), snap["screen"])
                back = rear.render(snap, t)
                self.assertEqual((back.size, back.mode), ((128, 64), "1"))
                self.assertIsNotNone(back.getbbox(), snap["screen"])
        self.assertEqual(seen, {"free", "busy", "setting", "focus", "on_air", "hey", "urgency"})

    def test_rear_wraps_long_messages(self):
        lines = wrap("UN MESSAGE ASSEZ LONG POUR TENIR SUR PLUSIEURS LIGNES SANS DEBORDER", 124)
        self.assertGreater(len(lines), 1)
        for line in lines:
            self.assertLessEqual(font.text_width(line), 124)
        self.assertTrue(all(font.text_width(l) <= 30 for l in wrap("ANTICONSTITUTIONNELLEMENT", 30)))

    def test_labels_fit_width(self):
        cfg = Config()
        for label in cfg.labels.values():
            self.assertLessEqual(font.text_width(label, 1), cfg.cols, label)


class ApiTest(unittest.TestCase):
    def setUp(self):
        self.cfg = Config()
        self.cfg.http_host, self.cfg.http_port, self.cfg.token = "127.0.0.1", 0, "s3cret"
        self.ind = Indicator(self.cfg)
        self.server = start_server(self.ind, self.cfg)
        self.base = "http://127.0.0.1:%d" % self.server.server_address[1]

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()

    def call(self, path, body=None, token="s3cret", raw=None):
        data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
        request = urllib.request.Request(self.base + path, data=data)
        if token:
            request.add_header("Authorization", "Bearer " + token)
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                return response.status, json.loads(response.read())
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    def test_status_is_public_but_posts_need_token(self):
        self.assertEqual(self.call("/api/status", token=None)[0], 200)
        self.assertEqual(self.call("/api/urgency", {}, token=None)[0], 401)
        self.assertEqual(self.call("/api/urgency", {}, token="faux")[0], 401)
        self.assertFalse(self.ind.snapshot()["urgency"])

    def test_routes(self):
        self.assertEqual(self.call("/api/mode", {"mode": "busy"})[1]["mode"], "busy")
        self.assertTrue(self.call("/api/on_air", {"on": True})[1]["on_air"])
        self.assertFalse(self.call("/api/on_air", {})[1]["on_air"])
        self.assertEqual(self.call("/api/hey", {"text": "Café ?"})[1]["hey_text"], "CAFE ?")
        self.assertEqual(self.call("/api/urgency", {})[1]["screen"], "urgency")
        self.assertEqual(self.call("/api/ack", {})[1]["screen"], "busy")
        status, snap = self.call("/api/timer", {"action": "start", "minutes": 50})
        self.assertEqual((status, snap["screen"], snap["timer"]["total"]), (200, "focus", 3000.0))
        self.assertEqual(self.call("/api/timer", {"action": "reset"})[1]["screen"], "busy")

    def test_bad_requests(self):
        self.assertEqual(self.call("/api/mode", {"mode": "dnd"})[0], 400)
        self.assertEqual(self.call("/api/on_air", {"on": "oui"})[0], 400)
        self.assertEqual(self.call("/api/timer", {"action": "explode"})[0], 400)
        self.assertEqual(self.call("/api/timer", {"action": "start", "minutes": "x"})[0], 400)
        self.assertEqual(self.call("/api/mode", raw=b"{pas du json")[0], 400)
        self.assertEqual(self.call("/api/mode", raw=b"[1]")[0], 400)
        self.assertEqual(self.call("/api/mode", raw=b" " * 5000)[0], 413)
        self.assertEqual(self.call("/api/inconnu", {})[0], 404)


try:
    import gpiozero
    from gpiozero.pins.mock import MockFactory, MockPWMPin
except ImportError:                                 # PC sans gpiozero
    gpiozero = None


@unittest.skipIf(gpiozero is None, "gpiozero absent")
class GpioTest(unittest.TestCase):
    """Boutons, molette et buzzer sur des broches simulées par gpiozero."""

    def setUp(self):
        import time
        from hey.inputs import GpioInputs

        self.sleep = time.sleep
        gpiozero.Device.pin_factory = MockFactory(pin_class=MockPWMPin)
        self.cfg = Config()
        self.cfg.hold_time = 0.2
        self.ind = Indicator(self.cfg)
        self.inputs = GpioInputs(self.cfg, self.ind)
        self.pin = gpiozero.Device.pin_factory.pin

    def tearDown(self):
        self.inputs.close()

    def tap(self, number, held=0.08):
        self.pin(number).drive_low()
        self.sleep(held)
        self.pin(number).drive_high()
        self.sleep(0.08)

    def test_switch_and_buttons(self):
        self.assertEqual(self.ind.mode, "free")
        self.pin(self.cfg.switch_pin).drive_low()
        self.sleep(0.08)
        self.assertEqual(self.ind.mode, "busy")
        self.pin(self.cfg.switch_pin).drive_high()
        self.sleep(0.08)
        self.assertEqual(self.ind.mode, "free")
        self.tap(self.cfg.button_pins["on_air"])
        self.assertTrue(self.ind.on_air)
        self.tap(self.cfg.button_pins["on_air"])
        self.assertFalse(self.ind.on_air)
        self.tap(self.cfg.button_pins["hey"])
        self.assertEqual(self.ind.snapshot()["screen"], "hey")
        self.tap(self.cfg.button_pins["urgency"])
        self.assertEqual(self.ind.snapshot()["screen"], "urgency")
        self.sleep(0.6)                             # laisse finir les bips

    def test_knob_press_and_hold(self):
        self.tap(self.cfg.encoder_sw_pin)
        self.assertEqual((self.ind.phase, self.ind.running), ("focus", True))
        self.tap(self.cfg.encoder_sw_pin)
        self.assertFalse(self.ind.running)
        self.tap(self.cfg.encoder_sw_pin, held=0.4)  # appui long : remise à zéro
        self.assertEqual(self.ind.phase, "idle")

    def test_mechanical_key(self):
        self.tap(self.cfg.key_pin)
        self.assertTrue(self.ind.running)
        self.tap(self.cfg.button_pins["urgency"])
        self.tap(self.cfg.key_pin)                  # acquitte sans toucher au minuteur
        self.assertEqual(self.ind.snapshot()["screen"], "focus")
        self.assertTrue(self.ind.running)
        self.tap(self.cfg.key_pin, held=0.4)
        self.assertEqual(self.ind.phase, "idle")
        self.sleep(0.6)

    def test_knob_rotation(self):
        a, b = self.pin(self.cfg.encoder_a_pin), self.pin(self.cfg.encoder_b_pin)

        def detent(first, second):
            for step in (first.drive_low, second.drive_low, first.drive_high, second.drive_high):
                step()
                self.sleep(0.01)

        detent(a, b)
        once = self.ind.focus_minutes
        self.assertEqual(abs(once - 25), 1)
        detent(b, a)
        self.assertEqual(self.ind.focus_minutes, 25)


try:
    import luma.oled  # noqa: F401
except ImportError:
    luma = None


@unittest.skipIf(luma is None, "luma.oled absent")
class OledTest(unittest.TestCase):
    """Le vrai pilote luma.oled, branché sur une interface factice."""

    def test_rear_display_sends_only_changes(self):
        from unittest import mock

        from luma.core.interface import serial

        from hey.display import OledDisplay

        cfg = Config()
        with mock.patch.object(serial, "i2c", lambda **kw: serial.noop()):
            oled = OledDisplay(cfg)
        sent = []
        oled._device.display = lambda image: sent.append(image)
        rear = RearRenderer(cfg)
        ind = Indicator(cfg)
        oled.show(rear.render(ind.snapshot(), 0.0))
        oled.show(rear.render(ind.snapshot(), 0.0))     # identique : rien n'est envoyé
        ind.urgency()
        oled.show(rear.render(ind.snapshot(), 0.0))
        self.assertEqual(len(sent), 2)
        oled.close()


if __name__ == "__main__":
    unittest.main()
