"""
PERMISSIONS.PY — Règles d'accès centralisées.

Avant la V2, la même condition était recopiée dans plusieurs vues.
La regrouper ici garantit qu'elle est identique partout et permet de la
tester une fois pour toutes (voir core/tests/test_permissions.py).
"""


def est_admin(user):
    return user.is_staff or user.is_superuser or user.role == "ADMIN"


def peut_voir_lot(user, batch):
    """Membre de l'entreprise du lot, ou contributeur assigné au lot."""
    if est_admin(user):
        return True
    return batch.client_id == user.client_id or batch.assigne_a_id == user.id


def peut_gerer_lot(user, batch):
    """Data scientist (ou admin) de l'entreprise du lot."""
    if est_admin(user):
        return True
    return user.is_data_scientist() and batch.client_id == user.client_id


def peut_voir_image(user, image):
    """
    Même règle que la galerie : images non supprimées du client de
    l'utilisateur ; un contributeur ne voit que ses propres dépôts.
    Les administrateurs (back-office) voient tout pour valider les dépôts.
    """
    if est_admin(user):
        return True
    if image.is_deleted or image.client_id != user.client_id:
        return False
    if user.role == "CONTRIB":
        return image.uploaded_by_id == user.id
    return True
