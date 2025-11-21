# Usa l'immagine ufficiale Kivy come base
FROM kivy/buildozer:latest

# Crea una variabile d'ambiente nel container che disattiva il controllo root
ENV BUILDOZER_ALLOW_ROOT=1

# (Opzionale, ma raccomandato per pulizia)
RUN pip install --upgrade pip buildozer
