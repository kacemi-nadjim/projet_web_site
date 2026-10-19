"""
MESURER_PAGES.PY — Mesure le poids réel des pages, comme un navigateur.

Ouvre un vrai navigateur (Chromium, via Playwright), se connecte, charge
chaque page, la fait défiler jusqu'en bas (pour déclencher le chargement
différé des images), puis relève :
  - le poids total transféré sur le réseau (Ko),
  - le nombre de requêtes HTTP,
  - le nombre d'éléments du DOM,
  - le temps de chargement,
et calcule l'EcoIndex correspondant.

Usage (le site doit tourner) :
    pip install playwright && playwright install chromium
    python outils/mesurer_pages.py http://127.0.0.1:8000 lea_ds demo1234 \
        /galerie/ /dashboard/ --sortie docs/mesures/pages.json
"""

import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ecoindex import ecoindex  # noqa: E402


def mesurer(base, identifiant, mdp, chemins, executable=None):
    from playwright.sync_api import sync_playwright

    resultats = {}
    with sync_playwright() as p:
        navigateur = p.chromium.launch(executable_path=executable)
        contexte = navigateur.new_context(viewport={"width": 1366, "height": 768})
        page = contexte.new_page()
        page.goto(base + "/compte/login/")
        page.fill("#id_username", identifiant)
        page.fill("#id_password", mdp)
        page.click("button[type=submit]")
        page.wait_for_load_state("networkidle")

        for chemin in chemins:
            # Cache vidé : on mesure une première visite (cas le plus lourd).
            cdp = contexte.new_cdp_session(page)
            cdp.send("Network.enable")
            cdp.send("Network.clearBrowserCache")
            octets, requetes = {"total": 0}, {"n": 0, "echecs": 0}

            def fin(ev, octets=octets):
                octets["total"] += ev.get("encodedDataLength", 0)

            def envoi(ev, requetes=requetes):
                requetes["n"] += 1

            def echec(ev, requetes=requetes):
                requetes["echecs"] += 1

            cdp.on("Network.loadingFinished", fin)
            cdp.on("Network.requestWillBeSent", envoi)
            cdp.on("Network.loadingFailed", echec)

            debut = time.perf_counter()
            page.goto(base + chemin)
            page.wait_for_load_state("networkidle")
            charge_ms = (time.perf_counter() - debut) * 1000
            # Défilement progressif jusqu'en bas de la page
            hauteur = page.evaluate("document.body.scrollHeight")
            for y in range(0, hauteur + 768, 600):
                page.evaluate(f"window.scrollTo(0, {y})")
                page.wait_for_timeout(120)
            page.wait_for_load_state("networkidle")
            page.wait_for_timeout(500)
            nb_dom = page.evaluate("document.getElementsByTagName('*').length")
            cdp.detach()

            ko = octets["total"] / 1024
            score, grade, ges, eau = ecoindex(nb_dom, requetes["n"], ko)
            resultats[chemin] = {
                "poids_ko": round(ko, 1), "requetes": requetes["n"],
                "requetes_echouees": requetes["echecs"], "dom": nb_dom,
                "chargement_ms": round(charge_ms), "ecoindex": score,
                "grade": grade, "ges_gco2e": ges, "eau_cl": eau,
            }
        navigateur.close()
    return resultats


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    parser.add_argument("base")
    parser.add_argument("identifiant")
    parser.add_argument("mot_de_passe")
    parser.add_argument("chemins", nargs="+")
    parser.add_argument("--sortie")
    parser.add_argument("--chromium", help="chemin d'un Chromium déjà installé")
    args = parser.parse_args()
    res = mesurer(args.base.rstrip("/"), args.identifiant, args.mot_de_passe,
                  args.chemins, args.chromium)
    texte = json.dumps(res, indent=2, ensure_ascii=False)
    print(texte)
    if args.sortie:
        Path(args.sortie).write_text(texte, encoding="utf-8")


if __name__ == "__main__":
    main()
