#!/usr/bin/env python3
"""hey-indicator v2 : indicateur de disponibilité à écran LED, façon BUSY Bar.

Sur le Raspberry Pi (en root, exigé par la dalle HUB75) :
    sudo python3 main.py

Sur n'importe quel PC, sans matériel (simulateur dans le terminal) :
    python3 main.py --sim
"""

import argparse
import signal
import sys
import threading
import time

from hey.api import start_server
from hey.config import Config
from hey.render import Renderer
from hey.state import Indicator


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--sim", action="store_true",
                        help="simulateur dans le terminal, commandes au clavier")
    parser.add_argument("--port", type=int, help="port de l'API HTTP")
    parser.add_argument("--host", help="adresse d'écoute de l'API HTTP")
    parser.add_argument("--no-api", action="store_true", help="ne pas lancer l'API HTTP")
    args = parser.parse_args()

    cfg = Config()
    if args.port:
        cfg.http_port = args.port
    if args.host:
        cfg.http_host = args.host

    indicator = Indicator(cfg)
    renderer = Renderer(cfg)
    stop = threading.Event()

    if args.sim:
        from hey.display import TerminalDisplay
        from hey.inputs import KEYS_HELP, KeyboardInputs

        display = TerminalDisplay(cfg)
        inputs = KeyboardInputs(cfg, indicator, stop.set)
        footer = KEYS_HELP
    else:
        from hey.display import Hub75Display
        from hey.inputs import GpioInputs

        display = Hub75Display(cfg)         # avant gpiozero : initialise en root
        inputs = GpioInputs(cfg, indicator)
        footer = ""

    server = None
    if not args.no_api:
        server = start_server(indicator, cfg, display)
        if not cfg.token and cfg.http_host not in ("127.0.0.1", "localhost", "::1"):
            print("Attention : API ouverte sans jeton (définir HEY_TOKEN).", file=sys.stderr)

    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    period = 1.0 / cfg.fps
    try:
        while not stop.is_set():
            started = time.monotonic()
            indicator.tick()
            display.show(renderer.render(indicator.snapshot()))
            if footer:
                sys.stdout.write("\x1b[0m" + footer + "\x1b[K\r\n")
                if server:
                    sys.stdout.write("API : http://%s:%d/\x1b[K\r\n" % server.server_address[:2])
                sys.stdout.flush()
            stop.wait(max(0.0, period - (time.monotonic() - started)))
    except KeyboardInterrupt:
        pass
    finally:
        if server:
            server.shutdown()
        inputs.close()
        display.close()
        print("Arrêt du programme")


if __name__ == "__main__":
    main()
