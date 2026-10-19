#!/usr/bin/env bash
# ============================================================
# DEPLOYER.SH — Mise en production d'une version de PixBank
# Usage (console Bash du serveur, environnement virtuel activé) :
#     bash outils/deployer.sh v1.1.0
# Chaque étape s'arrête à la première erreur (set -e) : le site en ligne
# n'est rechargé que si TOUT s'est bien passé.
# ============================================================
set -euo pipefail

VERSION="${1:?Préciser la version à déployer, par exemple : v1.1.0}"
WSGI="${PIXBANK_WSGI:-/var/www/nadjimkacemi_pythonanywhere_com_wsgi.py}"
URL="${PIXBANK_URL:-https://nadjimkacemi.pythonanywhere.com}"
cd "$(dirname "$0")/.."

[ -f .env ] || { echo "ERREUR : fichier .env absent (voir .env.exemple)"; exit 1; }

echo "== 1/8 Sauvegarde de sécurité avant mise à jour"
python manage.py sauvegarder

echo "== 2/8 Récupération du code de la version $VERSION"
git fetch --tags
git checkout "$VERSION"

echo "== 3/8 Dépendances"
pip install -r requirements.txt

echo "== 4/8 Migrations de la base de données"
python manage.py migrate --noinput

echo "== 5/8 Miniatures des images existantes"
python manage.py generer_miniatures

echo "== 6/8 Fichiers statiques (CSS, polices, JS)"
python manage.py collectstatic --noinput

echo "== 7/8 Contrôle de la configuration de production"
python manage.py check --deploy --fail-level WARNING

echo "== 8/8 Rechargement du site et vérification"
touch "$WSGI"
python - "$URL/sante/" <<'PY'
import json, sys, time, urllib.request
for essai in range(10):
    try:
        reponse = json.load(urllib.request.urlopen(sys.argv[1], timeout=10))
        print("Site en ligne :", reponse)
        sys.exit(0 if reponse.get("statut") == "ok" else 1)
    except Exception as exc:
        print("En attente du redémarrage...", exc)
        time.sleep(3)
sys.exit("ERREUR : le site ne répond pas — voir docs/INCIDENTS.md (retour arrière)")
PY
echo "Version $VERSION déployée."
