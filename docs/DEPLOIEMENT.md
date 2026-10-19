# Procédure de déploiement — PixBank

Hébergement actuel : **PythonAnywhere** (https://nadjimkacemi.pythonanywhere.com).
Le code de référence est le dépôt Git ; chaque version déployée correspond
à une étiquette (`v1.0.0`, `v1.1.0`…).

## 1. Principe : ne déployer que ce qui a été testé

```
poste de développement                              serveur de production
──────────────────────                              ─────────────────────
1. python manage.py test   (124 tests, SQLite et PostgreSQL)
2. ruff, bandit, pip-audit (0 alerte)
3. CHANGELOG + git tag v1.x.y + git push --tags  ─────►  bash outils/deployer.sh v1.x.y
                                                         (sauvegarde → code → dépendances →
                                                          migrations → miniatures → statiques →
                                                          check --deploy → rechargement → /sante/)
```

Le script `outils/deployer.sh` **s'arrête à la première erreur**. Le site
en ligne n'est rechargé que si toutes les étapes ont réussi. Il commence
toujours par une sauvegarde.

## 2. Première mise en place (passage du ZIP à Git) — à faire une fois

La v1.0 avait été déployée en envoyant un ZIP. Pour la v1.1, on passe au
déploiement par Git, ce qui permet de revenir à une version précédente en
une commande.

Dans une **console Bash** PythonAnywhere :
```bash
cd ~
git clone https://github.com/kacemi-nadjim/projet_web_site.git
cd projet_web_site
python3.10 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Reprendre les données de l'ancienne installation (adapter le chemin)
cp ~/ANCIEN_DOSSIER/db.sqlite3 .
cp -r ~/ANCIEN_DOSSIER/media .

# Créer le fichier des secrets à partir du modèle
cp .env.exemple .env
python -c "import secrets; print(secrets.token_urlsafe(50))"   # -> coller dans DJANGO_SECRET_KEY
nano .env
```

Dans l'onglet **Web** :

| Réglage | Valeur |
|---|---|
| Source code / Working directory | `/home/nadjimkacemi/projet_web_site` |
| Virtualenv | `/home/nadjimkacemi/projet_web_site/venv` |
| Static files | URL `/static/` → `/home/nadjimkacemi/projet_web_site/staticfiles` |
| **Static files `/media/`** | **SUPPRIMER cette ligne si elle existe.** Les photos doivent passer par Django, qui vérifie les droits (ANO-004). |
| Force HTTPS | activé |

Fichier WSGI (lien dans l'onglet Web), à remplacer **entièrement** par :
```python
import sys
sys.path.insert(0, "/home/nadjimkacemi/projet_web_site")
from config.wsgi import application   # lit les réglages dans .env
```

Puis lancer le premier déploiement : `bash outils/deployer.sh v1.1.0`.

## 3. Mise à jour courante

```bash
cd ~/projet_web_site && source venv/bin/activate
bash outils/deployer.sh v1.1.1
```

Ensuite :
- vérifier le numéro de version en pied de page ;
- faire un parcours rapide : connexion, galerie, export.

## 4. Retour arrière (si la nouvelle version pose problème)

**Cas 1 — la nouvelle version n'a pas modifié la base** (aucune migration) :
```bash
git checkout v1.1.0 && touch /var/www/nadjimkacemi_pythonanywhere_com_wsgi.py
```

**Cas 2 — la nouvelle version contenait une migration** : annuler la
migration **avant** de changer de code (l'ancien code ne la connaît pas).
```bash
python manage.py migrate core 0005     # exemple : retour au schéma de la v1.0
git checkout v1.0.0
touch /var/www/nadjimkacemi_pythonanywhere_com_wsgi.py
```
L'aller-retour de la migration 0006 a été testé sur SQLite et PostgreSQL.

**Cas 3 — données endommagées** :
```bash
python manage.py restaurer backups/pixbank_AAAAMMJJ_HHMMSS --confirmer
```
La sauvegarde prise automatiquement au début de chaque déploiement sert
de point de restauration.

## 5. Passage à PostgreSQL

Le code est prêt : il suffit de définir `DATABASE_URL` dans `.env`.
L'offre gratuite de PythonAnywhere ne propose pas PostgreSQL ; il faut
une offre payante ou un autre hébergeur.

1. Créer la base et un compte à privilèges minimaux : `docs/postgresql_setup.sql`.
2. Sauvegarder les données actuelles : `python manage.py sauvegarder`.
3. Ajouter `DATABASE_URL=postgres://…` dans `.env`, puis lancer `python manage.py migrate`.
4. Recharger les données : `python manage.py restaurer backups/pixbank_… --confirmer`.
   Le format de sauvegarde est indépendant du moteur.
5. Recharger le site, puis vérifier que `/sante/` renvoie `"base_de_donnees": "ok"`.

## 6. Tâches planifiées (onglet « Tasks »)

| Heure | Commande |
|---|---|
| 02:00 | `cd ~/projet_web_site && venv/bin/python manage.py sauvegarder` |
| 02:30 | `cd ~/projet_web_site && venv/bin/python manage.py purger_journal` |
| 02:45 | `cd ~/projet_web_site && venv/bin/python manage.py purger_images_supprimees` |

## 7. Supervision à activer

1. Créer un moniteur HTTP gratuit (UptimeRobot ou équivalent) sur
   `https://nadjimkacemi.pythonanywhere.com/sante/`, interrogé toutes les
   5 minutes, avec alerte par e-mail.
2. Renseigner `DJANGO_ADMINS` dans `.env` pour recevoir chaque erreur 500 par e-mail.
3. Vérifier que le journal s'écrit bien : `tail logs/pixbank.log`.
