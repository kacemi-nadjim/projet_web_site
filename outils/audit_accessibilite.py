"""
AUDIT_ACCESSIBILITE.PY — Audit automatique d'accessibilité (WCAG 2.1 A et AA).

Ouvre chaque page du site dans un vrai navigateur (Chromium piloté par
Playwright), y injecte le moteur d'audit axe-core (Deque Systems, utilisé
par Lighthouse) et liste les violations des règles WCAG 2.1 niveaux A et AA :
contrastes, textes alternatifs, étiquettes de formulaires, structure, ARIA...

Prérequis : python -m pip install playwright ; puis, une seule fois,
    cd outils/audits_web && npm install      (télécharge axe-core)
Usage (site lancé avec les données de démonstration dump.json) :
    python outils/audit_accessibilite.py --base http://127.0.0.1:8000 \
        --sortie resultats_accessibilite.json
Code de sortie : 0 si aucune violation, 1 sinon (utilisable avant un déploiement).
"""

import argparse
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

ICI = Path(__file__).resolve().parent
AXE = ICI / "audits_web" / "node_modules" / "axe-core" / "axe.min.js"

# (compte connecté ou None, adresse) — pages publiques puis pages privées
PAGES = [
    (None, "/"),
    (None, "/compte/login/"),
    (None, "/inscription/"),
    (None, "/contact/"),
    (None, "/mentions-legales/"),
    (None, "/confidentialite/"),
    (None, "/cgu/"),
    ("lea_ds", "/galerie/"),
    ("lea_ds", "/dashboard/"),
    ("lea_ds", "/lots/"),
    ("lea_ds", "/lots/1/"),
    ("lea_ds", "/lots/creer/"),
    ("lea_ds", "/compte/password_change/"),
    ("karim_contrib", "/deposer/"),
    ("karim_contrib", "/galerie/"),
    ("karim_contrib", "/lots/"),
]
NORMES = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://127.0.0.1:8000")
    parser.add_argument("--sortie", default=None, help="fichier JSON de résultats")
    parser.add_argument("--chromium", default=None, help="chemin d'un Chromium déjà installé")
    args = parser.parse_args()
    base = args.base.rstrip("/")
    if not AXE.is_file():
        sys.exit(f"axe-core introuvable ({AXE}) : lancer « npm install » dans outils/audits_web")
    script_axe = AXE.read_text(encoding="utf-8")

    resultats, total = [], 0
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=args.chromium)
        contextes = {}
        for compte, chemin in PAGES:
            if compte not in contextes:
                ctx = nav.new_context(viewport={"width": 1280, "height": 900})
                ctx.add_cookies([{"name": "cookie_ok", "value": "1", "url": base}])
                if compte:
                    pg = ctx.new_page()
                    pg.goto(base + "/compte/login/")
                    pg.fill("#id_username", compte)
                    pg.fill("#id_password", "demo1234")
                    pg.click("button[type=submit]")
                    pg.wait_for_load_state("networkidle")
                    pg.close()
                contextes[compte] = ctx
            pg = contextes[compte].new_page()
            reponse = pg.goto(base + chemin)
            pg.wait_for_load_state("networkidle")
            # L'injection passe par Playwright (et non par une balise <script>
            # de la page) : la politique CSP du site n'a pas à être assouplie.
            pg.evaluate(script_axe)
            rapport = pg.evaluate(
                "async (normes) => await axe.run(document, "
                "{runOnly: {type: 'tag', values: normes}})", NORMES)
            violations = [{
                "regle": v["id"], "impact": v["impact"], "description": v["help"],
                "elements": [n["target"][0] for n in v["nodes"]][:5],
                "nb_elements": len(v["nodes"]),
            } for v in rapport["violations"]]
            nb = sum(v["nb_elements"] for v in violations)
            total += nb
            resultats.append({"page": chemin, "compte": compte or "visiteur",
                              "statut_http": reponse.status if reponse else None,
                              "regles_reussies": len(rapport["passes"]),
                              "violations": violations})
            etat = "OK" if not violations else f"{nb} élément(s) en défaut"
            print(f"{chemin:<28} {compte or 'visiteur':<14} {etat}")
            for v in violations:
                print(f"    - [{v['impact']}] {v['regle']} : {v['description']} "
                      f"({v['nb_elements']}) {v['elements'][:3]}")
            pg.close()
        nav.close()

    print(f"\nPages auditées : {len(PAGES)} — éléments en défaut : {total}")
    if args.sortie:
        Path(args.sortie).write_text(json.dumps(
            {"outil": "axe-core", "normes": NORMES, "pages": resultats,
             "total_elements_en_defaut": total}, ensure_ascii=False, indent=2),
            encoding="utf-8")
    return 0 if total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
