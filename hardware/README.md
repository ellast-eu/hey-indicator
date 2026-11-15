# Matériel

## Pourquoi ce choix

La v1 tournait sur un Raspberry Pi avec 5 LED, 3 boutons et un interrupteur.
La v2 garde le Pi et Python, remplace les 5 LED par une dalle LED RGB, et
reprend deux idées du BUSY Bar : un petit écran monochrome au dos et une
touche de clavier mécanique sur le dessus.

| | BUSY Bar | hey-indicator v2 |
|---|---|---|
| Écran avant | matrice RGB 72x16 | dalle HUB75 64x32, pas de 2,5 mm (160 x 80 mm) |
| Écran arrière | OLED monochrome | OLED 1,3" 128x64 (SH1106, I2C) |
| Cerveau | STM32 + puce Wi-Fi | Raspberry Pi Zero 2 W (Wi-Fi, Python) |
| Commandes | touche, sélecteur, molette | touche mécanique, interrupteur Free/Busy, 3 poussoirs, molette |
| Son | haut-parleur | buzzer piézo passif |
| Alimentation | batterie 18650 | secteur 5 V (pas de batterie) |
| API | HTTP locale | HTTP locale (voir `hey/api.py`) |

Non repris : batterie, capteur de luminosité, Bluetooth, Matter.

Une dalle 64x32 est plus haute que la bande 72x16 du BUSY Bar : on y gagne
une seconde ligne (heure, minuteur, message), on y perd la silhouette en barre.
Une dalle 80x40 au pas de 4 mm a été essayée sur le papier : boîtier de
34 x 16,5 cm, jugé trop grand pour un bureau.

L'avant s'adresse aux autres (disponible ou pas) ; l'arrière, tourné vers la
personne au bureau, montre le minuteur détaillé, le message « Hey » en
entier, ce que fait la touche et l'adresse de l'API.

![Écran arrière](../docs/screens/arriere/planche.png)

## Liste de courses

Prix : ordres de grandeur non vérifiés, à contrôler chez ton revendeur.

| Pièce | Rôle | Ordre de prix |
|---|---|---|
| Raspberry Pi Zero 2 WH (connecteur soudé) + microSD 16 Go | cerveau | 30 € |
| Adafruit RGB Matrix Bonnet (réf. 3211) | pilotage de la dalle | 15-20 € |
| Dalle LED RGB HUB75 64x32, pas 2,5 mm, 160 x 80 mm, balayage 1/16 | écran avant | 20-30 € |
| OLED 1,3" 128x64 SH1106, I2C (4 broches) | écran arrière | 5-8 € |
| Switch mécanique compatible Cherry MX + capuchon (keycap) | touche du dessus | 2-5 € |
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

Le bonnet s'enfiche sur le Pi, la nappe HUB75 et les fils d'alimentation de la
dalle se branchent sur le bonnet. Le bonnet alimente aussi le Pi.

Le bonnet occupe les GPIO 4, 5, 6, 12, 13, 16, 17, 20, 21, 22, 23, 26, 27.
Les broches de la v1 ne sont donc plus libres :

| Fonction | GPIO (BCM) | Broche | v1 |
|---|---|---|---|
| Interrupteur Free/Busy | 19 | 35 | 19 (inchangé) |
| Touche mécanique | 15 | 10 | nouveau |
| Poussoir On Air | 25 | 22 | 5 |
| Poussoir Hey | 24 | 18 | 6 |
| Poussoir Urgency | 8 | 24 | 13 |
| Molette, voie A | 9 | 21 | nouveau |
| Molette, voie B | 10 | 19 | nouveau |
| Molette, poussoir | 11 | 23 | nouveau |
| Buzzer (+) | 7 | 26 | nouveau |
| OLED SDA | 2 | 3 | nouveau |
| OLED SCL | 3 | 5 | nouveau |
| OLED VCC | 3,3 V | 1 ou 17 | |
| Masse commune | GND | 6, 9, 14, 20, 25, 30, 34, 39 | |

- Chaque contact relie sa broche à la **masse** (pull-up interne). La v1
  reliait au 3,3 V avec pull-down : il faut recâbler.
- Au démarrage, le programme vérifie qu'aucune broche n'est prise deux fois ou
  par la dalle (`Config.check_pins`), et s'arrête avec un message sinon.
- Touche mécanique : les deux pattes du switch vont au GPIO 15 et à la masse.
  Le GPIO 15 est la réception de la liaison série : la laisser désactivée
  (c'est le cas par défaut).
- Les GPIO 7 à 11 sont ceux du SPI : le laisser désactivé (c'est le cas par
  défaut).
- GPIO 24 n'est libre que pour une dalle de 32 lignes (il sert de ligne
  d'adresse E aux dalles plus hautes).
- OLED : activer l'I2C (`sudo raspi-config`, Interface Options) et passer le
  bus à 400 kHz en ajoutant `dtparam=i2c_arm_baudrate=400000` dans
  `/boot/firmware/config.txt`. L'adresse est en général 0x3C
  (`i2cdetect -y 1` pour vérifier).
- Le bonnet ne ressort pas les broches libres : souder les fils sur les pattes
  du connecteur, côté dessous du Pi, ou intercaler un connecteur à broches
  longues.
- Buzzer : un piézo passif se branche directement entre GPIO 7 et la masse.
  Un buzzer magnétique demande un transistor.

## Installation sur le Pi

Non testé sur matériel réel : je n'ai fait tourner que le simulateur, et le
code de la dalle et de l'OLED avec des pilotes factices.

```sh
# Raspberry Pi OS Lite, Wi-Fi et SSH configurés
sudo apt install -y git python3-venv python3-pil python3-gpiozero wget
sudo git clone https://github.com/ellast-eu/hey-indicator /opt/hey-indicator
sudo chown -R "$USER" /opt/hey-indicator
cd /opt/hey-indicator
python3 -m venv env --system-site-packages
source env/bin/activate
pip install luma.oled

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
- `hey-corps.step`, `hey-capot.step`, `hey-assemblage.step` : pour retoucher en CAO.

`case/render_preview.py` produit l'aperçu `out/apercu.png`.

![Le boîtier](case/out/apercu.png)

Encombrement 180,4 x 85,4 x 62,4 mm : il faut un plateau d'au moins 185 mm.

Dessus, de gauche à droite vu de face : interrupteur Free/Busy, On Air,
touche mécanique au centre, Hey, Urgency. Molette sur le flanc droit. Au dos :
fenêtre de l'OLED, embase d'alimentation, ouïes.

C'est une ébauche à ajuster, pas un boîtier validé :

- les cotes de la dalle (épaisseur, zones d'appui au dos) varient d'un
  fabricant à l'autre : mesurer avant d'imprimer, tout est en tête de script ;
- la dalle est plaquée contre la fenêtre par quatre colonnettes du capot,
  elle n'est pas vissée ;
- la touche est une découpe de 14 mm pour switch Cherry MX, avec une paroi
  amincie à 1,5 mm pour les clips ;
- l'OLED est logé dans une cuvette au dos du capot et tenu à la colle chaude ;
  la position de l'écran sur la carte varie selon les modules
  (`OLED_PCB_OFFSET_Y`) ;
- pas de béquille ni d'inclinaison.
