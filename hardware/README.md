# Matériel

## Pourquoi ce choix

La v1 tournait sur un Raspberry Pi avec 5 LED, 3 boutons et un interrupteur.
La v2 garde le Pi et Python, et remplace les 5 LED par une dalle LED RGB.

| | BUSY Bar | hey-indicator v2 |
|---|---|---|
| Écran | matrice RGB 72x16 | dalle HUB75 64x32, pas de 2,5 mm (160 x 80 mm) |
| Cerveau | STM32 + puce Wi-Fi | Raspberry Pi Zero 2 W (Wi-Fi, Python) |
| Commandes | bouton, sélecteur de mode, molette | interrupteur Free/Busy, 3 poussoirs, molette |
| Son | haut-parleur | buzzer piézo passif |
| Alimentation | batterie 18650 | secteur 5 V (pas de batterie) |
| API | HTTP locale | HTTP locale (voir `hey/api.py`) |

Non repris : batterie, second écran OLED au dos, capteur de luminosité,
Bluetooth, Matter. Le capteur de luminosité est l'ajout le plus simple
(BH1750 sur l'I2C, broches 2 et 3 laissées libres).

Une dalle 64x32 est plus haute que la bande 72x16 du BUSY Bar : on y gagne
une seconde ligne (heure, minuteur, message), on y perd la silhouette en barre.

## Liste de courses

Prix : ordres de grandeur non vérifiés, à contrôler chez ton revendeur.

| Pièce | Rôle | Ordre de prix |
|---|---|---|
| Raspberry Pi Zero 2 WH (connecteur soudé) + microSD 16 Go | cerveau | 30 € |
| Adafruit RGB Matrix Bonnet (réf. 3211) | pilotage et alimentation de la dalle | 15-20 € |
| Dalle LED RGB HUB75 64x32, pas 2,5 mm, 160 x 80 mm, balayage 1/16 | écran | 20-30 € |
| Alimentation 5 V 4 A, fiche 5,5/2,1 mm | dalle + Pi | 12-15 € |
| Embase d'alimentation 5,5/2,1 mm à encastrer avec fiche mâle | traversée du capot | 3 € |
| Encodeur rotatif EC11 avec poussoir + bouton | molette | 2-3 € |
| 3 poussoirs momentanés à encastrer de 12 mm | On Air, Hey, Urgency | 5 € |
| Interrupteur à levier miniature (canon 6 mm) | Free/Busy | 2 € |
| Buzzer piézo passif | sons | 1 € |
| Plaque acrylique fumée 2 mm, 160 x 80 mm (facultatif) | contraste, aspect | 5 € |
| 4 inserts M3 à chaud, 4 vis M3x8, 4 vis M2,5x6, fils | assemblage | 5 € |

Si tu réutilises le Pi de la v1, vérifie seulement qu'il a un connecteur 40
broches ; ajuste alors `gpio_slowdown` dans `hey/config.py`.

## Câblage

Le bonnet s'enfiche sur le Pi, la nappe HUB75 et les deux fils d'alimentation
de la dalle se branchent sur le bonnet. Le bonnet alimente aussi le Pi.

Le bonnet occupe les GPIO 4, 5, 6, 12, 13, 16, 17, 20, 21, 22, 23, 26, 27.
Les broches de la v1 (17, 27, 22, 23, 24, 5, 6, 13) ne sont donc plus libres :

| Fonction | GPIO (BCM) | Broche | v1 |
|---|---|---|---|
| Interrupteur Free/Busy | 19 | 35 | 19 (inchangé) |
| Poussoir On Air | 25 | 22 | 5 |
| Poussoir Hey | 24 | 18 | 6 |
| Poussoir Urgency | 8 | 24 | 13 |
| Molette, voie A | 9 | 21 | nouveau |
| Molette, voie B | 10 | 19 | nouveau |
| Molette, poussoir | 11 | 23 | nouveau |
| Buzzer (+) | 7 | 26 | nouveau |
| Masse commune | GND | 6, 9, 14, 20, 25, 30, 34, 39 | |

- Chaque contact relie sa broche à la **masse** (pull-up interne). La v1
  reliait au 3,3 V avec pull-down : il faut recâbler.
- Les GPIO 7 à 11 sont ceux du SPI : le laisser désactivé (c'est le cas par
  défaut).
- GPIO 24 n'est libre que pour une dalle 64x32 (il sert aux dalles 64x64).
- Le bonnet ne ressort pas les broches libres : souder les fils sur les pattes
  du connecteur, côté dessous du Pi, ou intercaler un connecteur à broches
  longues.
- Buzzer : un piézo passif se branche directement entre GPIO 7 et la masse.
  Un buzzer magnétique demande un transistor.

## Installation sur le Pi

Non testé sur matériel réel : je n'ai fait tourner que le simulateur.

```sh
# Raspberry Pi OS Lite, Wi-Fi et SSH configurés
sudo apt install -y git python3-venv python3-pil python3-gpiozero wget
sudo git clone https://github.com/ellast-eu/hey-indicator /opt/hey-indicator
sudo chown -R "$USER" /opt/hey-indicator
cd /opt/hey-indicator
python3 -m venv env --system-site-packages
source env/bin/activate

# Bibliothèque de la dalle (script Adafruit : choisir « Bonnet » puis « convenience »)
pip3 install adafruit-python-shell
wget https://github.com/adafruit/Raspberry-Pi-Installer-Scripts/raw/main/rgb-matrix.py
sudo -E env PATH=$PATH python3 rgb-matrix.py

sudo env/bin/python main.py
```

Image qui scintille : essayer `gpio_slowdown` à 1, 2 ou 3, ou souder le pont
GPIO4-GPIO18 du bonnet et passer `hardware_mapping` à `adafruit-hat-pwm`.

Démarrage automatique : voir `systemd/hey-indicator.service`.

## Boîtier

`case/hey_case.py` (CadQuery) génère `case/out/` :

- `hey-corps.stl`, `hey-capot.stl` : à imprimer tels quels, sans supports ;
- `hey-corps.step`, `hey-capot.step`, `hey-assemblage.step` : pour retoucher en CAO ;
- `apercu.png` : rendu des deux pièces.

Encombrement 180,4 x 85,4 x 62,4 mm : il faut un plateau d'au moins 185 mm.

C'est une ébauche à ajuster, pas un boîtier validé :

- les cotes de la dalle (épaisseur, zones d'appui au dos) varient d'un
  fabricant à l'autre : mesurer avant d'imprimer, tout est en tête de script ;
- la dalle est plaquée contre la fenêtre par quatre colonnettes du capot,
  elle n'est pas vissée ;
- pas de béquille ni d'inclinaison ;
- les diamètres de perçage correspondent à des composants courants
  (poussoirs 12 mm, levier 6 mm, EC11, embase 8 mm).
