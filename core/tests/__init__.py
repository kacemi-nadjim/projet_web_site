"""
Tests automatisés de PixBank.

Lancer :           python manage.py test
Avec couverture :  coverage run manage.py test && coverage report

Organisation :
  test_regles_metier.py   les 12 tests de la V1 (règles critiques)
  test_securite.py        dépôt de fichiers, accès aux médias, force brute,
                          en-têtes, configuration de production
  test_images.py          dépôt, doublons, miniatures, galerie, export, dashboard
  test_lots.py            module de labélisation de bout en bout (vrais ZIP)
  test_qualite.py         moteur IoU (cas limites)
  test_performance.py     nombre de requêtes SQL constant (anti N+1), index utilisés
  test_maintenance.py     sauvegarde/restauration, purge, supervision, contraintes BDD
"""
