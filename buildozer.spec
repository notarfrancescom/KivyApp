[app]

# Titolo dell'app
title = Degustazione Vino

# Nome del pacchetto
package.name = WineTastingApp

# (str) Icon of the application
# Deve puntare al percorso del tuo file immagine
icon.filename = %(source.dir)s/icona.png

# (str) Presplash of the application
presplash.filename = %(source.dir)s/materiale/iniziale.png

# Dominio del pacchetto
package.domain = com.vino.kivyapp

# Directory sorgente
source.dir = .

# Include tutto ciò che è py, kv e tutta la cartella materiale
source.include_exts = py, png, jpg, kv, atlas, ttf
source.include_dirs = materiale

#--------------------------------------------------------------
# File da includere (estensioni nel root directory)
#source.include_exts = py,png,jpg,kv,atlas,ttf

# PATTERN PER INCLUDERE TUTTI I FILE NECESSARI
# La cartella 'materiale' è inclusa implicitamente nel pattern wildcard
# './*' include tutti i file nella root (es. main.py)
# 'materiale/*' include tutto il contenuto della cartella 'materiale'
source.include_patterns = ./*,materiale/*
#---------------------------------------------------------------

# Versione dell'app
version = 0.1

# Requisiti (aggiungi qui eventuali librerie extra)
#requirements = python3,kivy==2.3.1,filetype,tinydb
requirements = python3, kivy==2.3.0, sdl2, sdl2_image, sdl2_ttf, filetype, tinydb

# Versione Python (allineata al workflow)
python.version = 3.11

# Orientamento supportato
orientation = portrait

# Fullscreen
fullscreen = 1

# Permessi Android
android.permissions = android.permission.INTERNET

# Target API
android.api = 34

# Minima API supportata
android.minapi = 21

# ARCHITETTURE E RAMO P4A (Aggiungilo qui)
android.archs = arm64-v8a, armeabi-v7a
p4a.branch = master

# Versione NDK (compatibile con python-for-android)
android.ndk = 25b

# Percorso NDK (Lascia commentato se usi l'installazione automatica di buildozer)
# android.ndk_path = /home/runner/.buildozer/android/platform/android-ndk/25b

# Percorso SDK (Lascia commentato se usi l'installazione automatica di buildozer)
# android.sdk_path = /home/runner/.buildozer/android/platform/android-sdk

# API NDK
android.ndk_api = 21

# Architetture supportate
#android.archs = arm64-v8a, armeabi-v7a

# Backup
android.allow_backup = True

android.meta_data = kivy_graphics_engine=gles2

[buildozer]

# Livello di Log (2 = Info)
log_level = 2
