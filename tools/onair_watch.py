#!/usr/bin/env python3
"""Passe l'indicateur en « On Air » quand le micro ou la webcam du PC sert.

À lancer sur le PC (Linux), pas sur le Raspberry Pi :
    HEY_TOKEN=... python3 tools/onair_watch.py http://hey.local:8080

Micro   : flux de capture listés par `pactl` (PulseAudio ou PipeWire-Pulse).
Webcam  : compteur d'utilisation du module noyau uvcvideo.
NON TESTÉ sur une vraie machine : les deux sondes sont à valider chez toi.
"""

import json
import os
import subprocess
import sys
import time
import urllib.request

POLL_SECONDS = 2.0


def mic_in_use():
    try:
        out = subprocess.run(["pactl", "list", "short", "source-outputs"],
                             capture_output=True, text=True, timeout=3).stdout
    except (OSError, subprocess.SubprocessError):
        return False
    return bool(out.strip())


def camera_in_use():
    try:
        with open("/sys/module/uvcvideo/refcnt") as handle:
            return int(handle.read().strip()) > 0
    except (OSError, ValueError):
        return False


def set_on_air(base, on):
    request = urllib.request.Request(
        base.rstrip("/") + "/api/on_air",
        data=json.dumps({"on": on}).encode(),
        headers={"Content-Type": "application/json"})
    token = os.environ.get("HEY_TOKEN")
    if token:
        request.add_header("Authorization", "Bearer " + token)
    urllib.request.urlopen(request, timeout=3).close()


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    base, last = sys.argv[1], None
    while True:
        current = mic_in_use() or camera_in_use()
        if current != last:
            try:
                set_on_air(base, current)
                last = current
            except OSError as error:        # indicateur éteint : on réessaiera
                print("hey-indicator injoignable :", error, file=sys.stderr)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
