
[app]

# Titolo dell'app
title = My Application

# Nome del pacchetto
package.name = myapp

# Dominio del pacchetto
package.domain = com.vino.kivyapp

# Directory sorgente
source.dir = .

# File da includere
source.include_exts = py,png,jpg,kv,atlas

# Versione dell'app
version = 0.1

# Requisiti (aggiungi qui eventuali librerie extra)
requirements = python3,kivy

# Versione Python (allineata al workflow)
python.version = 3.10

# Orientamento supportato
orientation = portrait

# Fullscreen
fullscreen = 1

# Permessi Android (aggiungi se servono altri)
android.permissions = android.permission.INTERNET

# Target API (aggiornato)
android.api = 34

# Minima API supportata
android.minapi = 21

# Versione NDK (aggiornata)
android.ndk = 25c

# Percorso NDK (aggiornato)
android.ndk_path = /home/runner/.buildozer/android/platform/android-ndk/25c

# API NDK
android.ndk_api = 21

# Architetture supportate
android.archs = arm64-v8a, armeabi-v7a

# Backup
android.allow_backup = True


[buildozer]

# Log level
log_level = 2

# Avviso se root
warn_on_root = 0
