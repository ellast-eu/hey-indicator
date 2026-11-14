#!/usr/bin/env python3
"""Boîtier paramétrique de hey-indicator v2 (CadQuery).

    pip install cadquery
    python3 hardware/case/hey_case.py              # dalle 64x32
    python3 hardware/case/hey_case.py 80x40        # dalle Waveshare 80x40

Écrit STL + STEP dans hardware/case/out/<dalle>/.

Deux pièces à imprimer, sans supports :
  - corps  : face avant posée sur le plateau ;
  - capot  : face extérieure posée sur le plateau.

Dessus : interrupteur Free/Busy, touche mécanique (type Cherry MX), poussoirs
On Air, Hey, Urgency. Flanc droit : molette. Capot : écran OLED arrière,
embase d'alimentation, ouïes.

Repère : X = largeur, Y = hauteur, Z = profondeur (z = 0 : face avant).
Toutes les cotes sont en millimètres. MESURER la dalle et les composants
réellement reçus avant d'imprimer : les cotes ci-dessous sont des valeurs
courantes, pas celles d'une référence précise.
"""

import os
import sys

import cadquery as cq

# Taille des dalles (mm). Épaisseur non publiée par Waveshare pour la 80x40 :
# 15 mm est une hypothèse à vérifier sur la dalle reçue.
PANELS = {
    "64x32": {"w": 160.0, "h": 80.0, "d": 15.0},
    "80x40": {"w": 320.0, "h": 160.0, "d": 15.0},
}

CLEAR = 0.3             # jeu autour de la dalle
LIP = 0.6               # recouvrement de la fenêtre sur le bord de la dalle
SMOKED_T = 2.0          # plaque acrylique fumée devant la dalle (0 = aucune)

# --- Coque --------------------------------------------------------------------
WALL = 2.4
FRONT_T = 2.0
CHEEK = 7.5             # marge latérale : loge les 4 colonnes de vissage
POST_H = 9.0
DEPTH_IN = 58.0         # profondeur intérieure (dalle + câbles + Pi et bonnet)
COVER_T = 2.4
CORNER_R = 4.0
INSERT_D = 4.0          # perçage pour insert fileté M3 à chaud
INSERT_DEPTH = 8.0
SCREW_D = 3.4           # passage de vis M3 dans le capot

# --- Commandes du dessus --------------------------------------------------------
CTRL_Z = 40.0           # distance des commandes à la face avant
CTRL_PITCH = 32.0       # entraxe maximal entre deux commandes
BUTTON_D = 12.2         # poussoirs à encastrer de 12 mm (On Air, Hey, Urgency)
SWITCH_D = 6.2          # interrupteur à levier Free/Busy (canon de 6 mm)
KEY_HOLE = 14.0         # touche Cherry MX ou compatible : découpe carrée de 14 mm
KEY_PLATE = 1.5         # épaisseur de plaque exigée par les clips du switch
KEY_POCKET = 16.5       # dégagement des clips, côté intérieur
ENCODER_D = 7.2         # encodeur EC11 (canon M7), sur le flanc droit
# Ordre de gauche à droite, vu de face.
TOP_CONTROLS = ("switch", "on_air", "key", "hey", "urgency")

# --- Capot arrière ------------------------------------------------------------
PI_HOLES = (58.0, 23.0)  # entraxes de fixation du Pi Zero (vis M2,5)
PI_CENTER = (-25.0, -18.0)
PI_STANDOFF_H = 6.0
PI_STANDOFF_D = 6.0
PI_PILOT_D = 2.2        # avant-trou pour vis M2,5 autotaraudeuse
JACK_D = 8.2            # embase d'alimentation 5,5/2,1 mm à encastrer
JACK_POS = (60.0, -20.0)
PUSHER_D = 8.0          # colonnettes qui plaquent la dalle contre la fenêtre
PUSHER_FRAC = (0.45, 0.41)  # position, en fraction de la taille de la dalle
VENT = (24.0, 2.5, 5, 6.0)  # longueur, largeur, nombre, pas des ouïes
VENT_POS = (50.0, 8.0)      # centre de la première ouïe

# Écran OLED 1,3" 128x64 (SH1106, I2C). Le module est logé dans une
# cuvette côté intérieur et tenu à la colle chaude ou par deux brides.
OLED_POS = (0.0, 18.0)      # centre de la zone active, vu de l'intérieur
OLED_WINDOW = (31.0, 16.5)  # zone active 29,4 x 14,7 + marge
OLED_PCB = (36.0, 34.5)     # carte du module, avec jeu
OLED_PCB_OFFSET_Y = 2.0     # carte décentrée vers ses broches (en haut) : à mesurer
OLED_SKIN = 1.0             # épaisseur restante devant l'écran

PANEL = None


def configure(panel):
    """Calcule toutes les cotes pour une dalle (variables du module)."""
    if panel not in PANELS:
        raise SystemExit("dalle inconnue : %s (connues : %s)" % (panel, ", ".join(PANELS)))
    size = PANELS[panel]
    values = {"PANEL": panel, "PANEL_W": size["w"], "PANEL_H": size["h"], "PANEL_D": size["d"]}
    values["CAV_W"] = values["PANEL_W"] + 2 * CLEAR + 2 * CHEEK
    values["CAV_H"] = values["PANEL_H"] + 2 * CLEAR
    values["OUTER_W"] = values["CAV_W"] + 2 * WALL
    values["OUTER_H"] = values["CAV_H"] + 2 * WALL
    values["BODY_D"] = FRONT_T + DEPTH_IN
    values["POST_X"] = values["CAV_W"] / 2 - CHEEK / 2
    values["POST_Y"] = values["CAV_H"] / 2 - POST_H / 2
    values["PUSHER_LEN"] = DEPTH_IN - values["PANEL_D"] - SMOKED_T - 0.3
    values["PUSHER_POS"] = (PUSHER_FRAC[0] * values["PANEL_W"],
                            PUSHER_FRAC[1] * values["PANEL_H"])
    span = values["CAV_W"] - 2 * CHEEK - 2 * BUTTON_D
    pitch = min(CTRL_PITCH, span / (len(TOP_CONTROLS) - 1))
    first = -pitch * (len(TOP_CONTROLS) - 1) / 2
    values["CONTROL_X"] = {name: first + index * pitch
                           for index, name in enumerate(TOP_CONTROLS)}
    globals().update(values)


configure(os.environ.get("HEY_PANEL", "64x32"))


def cylinder(diameter, length, origin, direction):
    return cq.Workplane("XY").add(
        cq.Solid.makeCylinder(diameter / 2, length, cq.Vector(*origin), cq.Vector(*direction)))


def corners():
    return [(sx, sy) for sx in (-1, 1) for sy in (-1, 1)]


def make_body():
    body = (cq.Workplane("XY")
            .box(OUTER_W, OUTER_H, BODY_D, centered=(True, True, False))
            .edges("|Z").fillet(CORNER_R))
    cavity = (cq.Workplane("XY").workplane(offset=FRONT_T)
              .box(CAV_W, CAV_H, DEPTH_IN + 1, centered=(True, True, False)))
    window = (cq.Workplane("XY").workplane(offset=-1)
              .box(PANEL_W - 2 * LIP, PANEL_H - 2 * LIP, FRONT_T + 2, centered=(True, True, False)))
    body = body.cut(cavity).cut(window)

    # Colonnes de vissage : dans les marges latérales, elles guident aussi la dalle.
    overlap = 0.5
    for sx, sy in corners():
        post = (cq.Workplane("XY").workplane(offset=FRONT_T - overlap)
                .center(sx * (POST_X + overlap / 2), sy * (POST_Y + overlap / 2))
                .box(CHEEK + overlap, POST_H + overlap, DEPTH_IN + overlap,
                     centered=(True, True, False)))
        body = body.union(post)
    for sx, sy in corners():
        body = body.cut(cylinder(INSERT_D, INSERT_DEPTH + 1,
                                 (sx * POST_X, sy * POST_Y, BODY_D - INSERT_DEPTH), (0, 0, 1)))

    # Dessus : interrupteur, touche mécanique et poussoirs.
    top = OUTER_H / 2
    for name, x in CONTROL_X.items():
        if name == "key":
            body = body.cut(cq.Workplane("XY").box(KEY_HOLE, WALL + 2, KEY_HOLE)
                            .translate((x, top - WALL / 2, CTRL_Z)))
            # Cuvette intérieure : ramène la paroi à l'épaisseur d'une plaque.
            pocket_depth = WALL - KEY_PLATE
            body = body.cut(cq.Workplane("XY").box(KEY_POCKET, pocket_depth + 1, KEY_POCKET)
                            .translate((x, top - WALL + (pocket_depth - 1) / 2, CTRL_Z)))
        else:
            diameter = SWITCH_D if name == "switch" else BUTTON_D
            body = body.cut(cylinder(diameter, WALL + 2, (x, top - WALL - 1, CTRL_Z), (0, 1, 0)))

    # Flanc droit : molette (encodeur rotatif).
    body = body.cut(cylinder(ENCODER_D, WALL + 2, (OUTER_W / 2 - WALL - 1, 0, CTRL_Z), (1, 0, 0)))
    return body


def make_cover():
    """Capot dans le repère d'assemblage : plaque en z = BODY_D .. BODY_D + COVER_T."""
    cover = (cq.Workplane("XY").workplane(offset=BODY_D)
             .box(OUTER_W, OUTER_H, COVER_T, centered=(True, True, False))
             .edges("|Z").fillet(CORNER_R))

    # Entretoises du Pi Zero 2 W (le bonnet s'enfiche dessus, vers l'avant).
    for sx, sy in corners():
        x = PI_CENTER[0] + sx * PI_HOLES[0] / 2
        y = PI_CENTER[1] + sy * PI_HOLES[1] / 2
        cover = cover.union(cylinder(PI_STANDOFF_D, PI_STANDOFF_H + 0.2,
                                     (x, y, BODY_D + 0.2), (0, 0, -1)))
        cover = cover.cut(cylinder(PI_PILOT_D, PI_STANDOFF_H + 1.5,
                                   (x, y, BODY_D + 1.3), (0, 0, -1)))

    # Colonnettes de maintien de la dalle.
    for sx, sy in corners():
        cover = cover.union(cylinder(PUSHER_D, PUSHER_LEN + 0.2,
                                     (sx * PUSHER_POS[0], sy * PUSHER_POS[1], BODY_D + 0.2),
                                     (0, 0, -1)))

    # Vis M3 vers les inserts du corps.
    for sx, sy in corners():
        cover = cover.cut(cylinder(SCREW_D, COVER_T + 2,
                                   (sx * POST_X, sy * POST_Y, BODY_D - 1), (0, 0, 1)))

    # Écran arrière : fenêtre traversante + cuvette pour la carte du module.
    pocket_depth = COVER_T - OLED_SKIN
    cover = cover.cut(cq.Workplane("XY")
                      .box(OLED_PCB[0], OLED_PCB[1], pocket_depth + 0.5,
                           centered=(True, True, False))
                      .translate((OLED_POS[0], OLED_POS[1] + OLED_PCB_OFFSET_Y, BODY_D - 0.5)))
    cover = cover.cut(cq.Workplane("XY")
                      .box(OLED_WINDOW[0], OLED_WINDOW[1], COVER_T + 2,
                           centered=(True, True, False))
                      .translate((OLED_POS[0], OLED_POS[1], BODY_D - 1)))

    # Embase d'alimentation et ouïes d'aération.
    cover = cover.cut(cylinder(JACK_D, COVER_T + 2,
                               (JACK_POS[0], JACK_POS[1], BODY_D - 1), (0, 0, 1)))
    length, width, count, pitch = VENT
    for index in range(count):
        slot = (cq.Workplane("XY").workplane(offset=BODY_D - 1)
                .center(VENT_POS[0], VENT_POS[1] + index * pitch)
                .slot2D(length, width).extrude(COVER_T + 2))
        cover = cover.cut(slot)
    return cover


def make_panel():
    """Volume de la dalle, pour l'aperçu et les contrôles de collision."""
    return (cq.Workplane("XY").workplane(offset=FRONT_T + SMOKED_T)
            .box(PANEL_W, PANEL_H, PANEL_D, centered=(True, True, False)))


def main():
    if len(sys.argv) > 1:
        configure(sys.argv[1])
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "out", PANEL)
    os.makedirs(out, exist_ok=True)
    body, cover = make_body(), make_cover()
    # Capot retourné pour l'impression : face extérieure sur le plateau.
    cover_print = cover.rotate((0, 0, 0), (1, 0, 0), 180).translate((0, 0, BODY_D + COVER_T))

    cq.exporters.export(body, os.path.join(out, "hey-corps.stl"), tolerance=0.05)
    cq.exporters.export(cover_print, os.path.join(out, "hey-capot.stl"), tolerance=0.05)
    cq.exporters.export(body, os.path.join(out, "hey-corps.step"))
    cq.exporters.export(cover, os.path.join(out, "hey-capot.step"))
    assembly = (cq.Assembly()
                .add(body, name="corps", color=cq.Color(0.15, 0.15, 0.17))
                .add(cover, name="capot", color=cq.Color(0.15, 0.15, 0.17))
                .add(make_panel(), name="dalle", color=cq.Color(0.02, 0.02, 0.02)))
    assembly.export(os.path.join(out, "hey-assemblage.step"))
    print("Dalle %s, encombrement : %.1f x %.1f x %.1f mm"
          % (PANEL, OUTER_W, OUTER_H, BODY_D + COVER_T))
    print("Fichiers écrits dans", out)


if __name__ == "__main__":
    main()
