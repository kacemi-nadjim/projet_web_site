# Gestion des incidents de production — PixBank

Un **incident** est un dysfonctionnement constaté sur le site **en ligne**.
Les anomalies trouvées pendant les tests, avant mise en production, sont
suivies dans [REGISTRE_ANOMALIES.md](REGISTRE_ANOMALIES.md).

## 1. Niveaux de gravité et délais

| Niveau | Exemple | Prise en charge | Correction visée |
|---|---|---|---|
| **P1 — Bloquant** | Site inaccessible, fuite de données, faille exploitée | Immédiate | Contournement sous 4 h, correctif sous 24 h |
| **P2 — Majeur** | Une fonctionnalité clé est cassée (export, dépôt, contrôle qualité) | Dans la journée | Sous 72 h |
| **P3 — Mineur** | Défaut d'affichage, lenteur ponctuelle | Prochaine version | Version corrective suivante |

## 2. Processus

1. **Détection** : alerte `/sante/`, e-mail d'erreur 500, journal ou signalement d'un utilisateur.
2. **Qualification** : gravité (P1/P2/P3), périmètre (quels clients, depuis quand).
3. **Contournement** : si P1, revenir à la version précédente (`git checkout` de
   l'étiquette précédente + rechargement, voir [DEPLOIEMENT.md](DEPLOIEMENT.md)).
4. **Analyse de la cause racine** : la cause réelle, pas seulement le symptôme.
5. **Correctif + test de non-régression** : le correctif est livré **avec** un
   test automatisé qui échouerait si le problème revenait.
6. **Déploiement** : nouvelle version corrective (ex. 1.1.0 → 1.1.1), CHANGELOG à jour.
7. **Clôture** : fiche ci-dessous complétée. Si l'incident relève une
   faiblesse du processus, la procédure est corrigée.

## 3. Modèle de fiche

```
INC-XXX — Titre court
Date de détection / de résolution :
Gravité : P1 / P2 / P3       Détecté par :
Symptôme :
Cause racine :
Correctif :
Test de non-régression :
Action d'amélioration du processus :
```

## 4. Incidents réels

### INC-001 — Back-office affiché sans mise en forme après le déploiement
- **Période** : fin août 2026, premier déploiement sur PythonAnywhere.
- **Gravité** : P2 (back-office utilisable mais très difficile à lire,
  validation des dépôts ralentie).
- **Symptôme** : les pages `/admin/` s'affichaient sans aucun style.
- **Cause racine** : en production, les fichiers CSS ne sont pas servis par
  Django. Ils doivent être rassemblés par `collectstatic` dans le dossier
  `STATIC_ROOT`, que le serveur web publie. Ce paramètre n'était pas défini.
- **Correctif** : `STATIC_ROOT` défini, `collectstatic` exécuté, dossier
  déclaré dans la configuration du serveur web.
- **Faiblesse du processus relevée en octobre 2026** : la correction avait
  été faite **sur le serveur**, mais elle ne figurait pas dans le code
  versionné (le `settings.py` du dépôt n'avait toujours pas de
  `STATIC_ROOT`). Un nouveau déploiement aurait reproduit l'incident.
- **Amélioration** : `STATIC_ROOT` est désormais dans `settings.py`
  (v1.1), et `collectstatic` fait partie du script de déploiement
  `outils/deployer.sh`. Règle adoptée : **aucune modification de
  configuration directement sur le serveur** sans report dans le dépôt Git.

### INC-002 — Messages du formulaire de contact perdus
- **Période** : fin août 2026, constaté en testant le site avant la soutenance.
- **Gravité** : P2 (perte silencieuse de demandes de visiteurs).
- **Symptôme** : le visiteur voyait « message envoyé », mais
  l'administrateur ne recevait rien et ne trouvait rien.
- **Cause racine** : le formulaire était validé, puis le message était
  abandonné : il n'était enregistré nulle part.
- **Correctif** : modèle `MessageContact` (migration 0005) et écran de
  traitement dans le back-office (case « traité »).
- **Test de non-régression** (ajouté en v1.1) :
  `test_images.ContactTest.test_message_enregistre_en_base`, complété par
  le test du champ anti-robot et celui du consentement obligatoire.
- **Amélioration** : chaque fonctionnalité qui enregistre une donnée doit
  avoir un test qui vérifie la présence de cette donnée **en base**, et
  pas seulement le message affiché.

## 5. Outils de diagnostic

| Question | Où chercher |
|---|---|
| Le site et la base répondent-ils ? | `https://<site>/sante/` |
| Quelle version tourne ? | pied de page, ou `/sante/` |
| Quelle erreur s'est produite ? | e-mail aux administrateurs, `logs/pixbank.log` |
| Qui a accédé à quoi, quand ? | back-office → Journal d'accès (filtres par événement et par date) |
| Les données sont-elles intactes ? | `python manage.py restaurer <sauvegarde>` vérifie d'abord les empreintes SHA-256 |
