[app]

# (str) Title of your application
title = My Application

# (str) Package name
package.name = myapp

# (str) Package domain (needed for android/ios packaging)
package.domain = org.test

# (str) Source code where the main.py live
source.dir = .

# (list) Source files to include
source.include_exts = py,png,jpg,kv,atlas

# (str) Application versioning
version = 0.1

# (list) Application requirements
requirements = python3,kivy==2.1.0

# (str) Versione Python da compilare (CRUCIALE per evitare errori NDK)
python.version = 3.9  # ALLINEATO AL RUNNER DI GITHUB ACTIONS

# (list) Supported orientations
orientation = portrait

#
# Android specific
#

# (bool) Indicate if the application should be fullscreen or not
fullscreen = 1

# (list) Permissions
android.permissions = android.permission.INTERNET

# (int) Target Android API, dovrebbe essere il più alto possibile.
android.api = 33

# (int) Minimum API your APK / AAB will support.
android.minapi = 21

# (str) Android NDK version to use
android.ndk = 23b

# (int) Android NDK API to use. Deve corrispondere a android.minapi.
android.ndk_api = 21

# (list) The Android archs to build for
android.archs = arm64-v8a, armeabi-v7a

# (bool) enables Android auto backup feature
android.allow_backup = True


[buildozer]

# (int) Log level (2 = debug, utile per il CI)
log_level = 2

# (int) Display warning if buildozer is run as root (1 = True)
warn_on_root = 0

# (str) FORZA L'USO DI UN BRANCH PIÙ STABILE DI PYTHON-FOR-ANDROID
# p4a.branch = develop

# (str) FORZA L'USO DELLA FORK UFFICIALE DI KIVY CON LA PATCH DI FIX
# p4a.url = https://github.com/kivy/python-for-androida
