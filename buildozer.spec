[app]

# Titolo dell'app
title = My Application

# Nome del pacchetto
package.name = myapp

# Dominio del pacchetto
package.domain = com.vino.kivyapp

# Directory sorgente
source.dir = .

# File da includere (estensioni nel root directory)
source.include_exts = py,png,jpg,kv,atlas,ttf

# PATTERN PER INCLUDERE TUTTI I FILE NECESSARI
# La cartella 'materiale' è inclusa implicitamente nel pattern wildcard
# './*' include tutti i file nella root (es. main.py)
# 'materiale/*' include tutto il contenuto della cartella 'materiale'
source.include_patterns = ./*,materiale/*

# Versione dell'app
version = 0.1

# Requisiti (aggiungi qui eventuali librerie extra)
requirements = python3,kivy==2.3.1,filetype,tinydb

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

# Versione NDK (compatibile con python-for-android)
android.ndk = 25b

# Percorso NDK (Lascia commentato se usi l'installazione automatica di buildozer)
# android.ndk_path = /home/runner/.buildozer/android/platform/android-ndk/25b

# Percorso SDK (Lascia commentato se usi l'installazione automatica di buildozer)
# android.sdk_path = /home/runner/.buildozer/android/platform/android-sdk

# API NDK
android.ndk_api = 21

# Architetture supportate
android.archs = arm64-v8a, armeabi-v7a

# Backup
android.allow_backup = True


[buildozer]

# Livello di Log (2 = Info)
log_level = 2
