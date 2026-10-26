#!/usr/bin/env bash
# Render Build Command: ./build.sh
# Installiert Abhängigkeiten, sammelt statische Dateien und führt
# Datenbank-Migrationen aus (z. B. die Archiv-Tabelle der Mediathek).
set -o errexit

pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
