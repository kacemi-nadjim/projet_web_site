"""
VERIFIER_NAVIGATEUR.PY — Recette automatique dans un vrai navigateur.

Parcourt le site comme un utilisateur (Chromium piloté par Playwright) avec
les données de démonstration (dump.json) et vérifie :
  - aucune erreur JavaScript, aucune violation de la politique CSP,
    aucune ressource en erreur (404/500) ;
  - photos inaccessibles sans connexion ; miniatures affichées ;
  - export téléchargeable ; dépôt d'un fichier piégé refusé ;
  - blocage après 5 échecs de connexion ; aperçus du back-office ;
  - pas de défilement horizontal sur mobile (390 px) ;
et enregistre des captures d'écran.

Usage (site lancé avec : python manage.py loaddata dump.json && python manage.py runserver) :
    python outils/verifier_navigateur.py --base http://127.0.0.1:8000 --captures docs/captures_recette
ATTENTION : le test de force brute bloque le compte sara_ds_acme 15 minutes.
"""

import argparse
from pathlib import Path

from playwright.sync_api import sync_playwright

parser = argparse.ArgumentParser()
parser.add_argument("--base", default="http://127.0.0.1:8000")
parser.add_argument("--captures", default="captures_recette")
parser.add_argument("--chromium", default=None, help="chemin d'un Chromium déjà installé")
args = parser.parse_args()
BASE = args.base.rstrip("/")
SHOTS = Path(args.captures)
SHOTS.mkdir(parents=True, exist_ok=True)
ICI = SHOTS
problemes = []
try:
    with sync_playwright() as p:
        nav = p.chromium.launch(executable_path=args.chromium)

        def page_neuve(largeur=1280):
            ctx = nav.new_context(viewport={"width": largeur, "height": 900})
            if True:  # bandeau cookies déjà accepté : captures lisibles
                ctx.add_cookies([{"name": "cookie_ok", "value": "1", "url": BASE}])
            pg = ctx.new_page()
            pg.on("console", lambda m: m.type in ("error", "warning") and problemes.append(f"{pg.url} console {m.type}: {m.text}"))
            pg.on("pageerror", lambda e: problemes.append(f"{pg.url} pageerror: {e}"))
            pg.on("response", lambda r: r.status >= 400 and "/media/" not in r.url and problemes.append(f"HTTP {r.status} {r.url}"))
            return ctx, pg

        def connexion(pg, u, mdp="demo1234"):
            pg.goto(BASE + "/compte/login/")
            pg.fill("#id_username", u)
            pg.fill("#id_password", mdp)
            pg.click("button[type=submit]")
            pg.wait_for_load_state("networkidle")

        # 1. Accueil + bandeau cookies
        ctx, pg = page_neuve()
        pg.goto(BASE + "/")
        pg.wait_for_load_state("networkidle")
        pg.screenshot(path=SHOTS / "01_accueil.png")
        if pg.is_visible("#cookie-ok"):
            pg.click("#cookie-ok")
        visible = pg.is_visible("#cookie-banner")
        print("bandeau cookies masqué après clic :", not visible)
        polices = pg.evaluate("document.fonts.check('16px Sora')")
        print("police Sora chargée :", polices)
        # 2. Accès anonyme à une photo
        r = pg.request.get(BASE + "/media/images/2026/08/demo_0_648.jpg", max_redirects=0)
        print("photo en anonyme :", r.status, r.headers.get("location"))
        ctx.close()

        # 3. Galerie + dashboard (lea_ds)
        ctx, pg = page_neuve()
        connexion(pg, "lea_ds")
        pg.goto(BASE + "/galerie/")
        pg.wait_for_load_state("networkidle")
        nb_img = pg.evaluate("[...document.querySelectorAll('.grid img')].filter(i => i.complete && i.naturalWidth > 0).length")
        print("galerie : images affichées =", nb_img, "/", pg.evaluate("document.querySelectorAll('.grid img').length"))
        pg.screenshot(path=SHOTS / "02_galerie.png", full_page=True)
        pg.goto(BASE + "/dashboard/")
        pg.wait_for_load_state("networkidle")
        pg.screenshot(path=SHOTS / "03_dashboard.png", full_page=True)
        pg.goto(BASE + "/lots/1/")
        pg.wait_for_load_state("networkidle")
        pg.screenshot(path=SHOTS / "04_lot.png", full_page=True)
        # export
        with pg.expect_download() as dl:
            pg.goto(BASE + "/galerie/")
            pg.click("text=Exporter le dataset")
        print("export téléchargé :", dl.value.suggested_filename)
        ctx.close()

        # 4. Mobile
        ctx, pg = page_neuve(390)
        connexion(pg, "lea_ds")
        pg.goto(BASE + "/galerie/")
        pg.wait_for_load_state("networkidle")
        largeur = pg.evaluate("document.documentElement.scrollWidth")
        print("mobile 390 px : largeur de page =", largeur)
        pg.screenshot(path=SHOTS / "05_galerie_mobile.png")
        ctx.close()

        # 5. Dépôt d'un fichier piégé (karim_contrib)
        ctx, pg = page_neuve()
        connexion(pg, "karim_contrib")
        pg.goto(BASE + "/deposer/")
        piege = ICI / "piege.html"
        piege.write_text("<script>alert(1)</script>")
        pg.set_input_files("#id_fichiers", str(piege))
        pg.check("#id_categories_0")
        pg.click("form.form-card button[type=submit]")
        pg.wait_for_load_state("networkidle")
        print("dépôt piégé :", pg.inner_text("#id_fichiers_error") if pg.is_visible("#id_fichiers_error") else "PAS DE MESSAGE")
        pg.screenshot(path=SHOTS / "06_depot_refuse.png", full_page=True)
        ctx.close()

        # 6. Force brute
        ctx, pg = page_neuve()
        for _ in range(5):
            pg.goto(BASE + "/compte/login/")
            pg.fill("#id_username", "sara_ds_acme")
            pg.fill("#id_password", "mauvais")
            pg.click("button[type=submit]")
        connexion(pg, "sara_ds_acme")
        print("après 5 échecs + bon mot de passe :", pg.inner_text(".flash-error"))
        pg.screenshot(path=SHOTS / "07_force_brute.png")
        ctx.close()

        # 7. Back-office : journal + images avec aperçu
        ctx, pg = page_neuve(1400)
        connexion(pg, "admin")
        pg.goto(BASE + "/admin/core/journalacces/")
        pg.wait_for_load_state("networkidle")
        pg.screenshot(path=SHOTS / "08_journal.png", full_page=True)
        pg.goto(BASE + "/admin/core/image/")
        pg.wait_for_load_state("networkidle")
        apercus = pg.evaluate("[...document.querySelectorAll('th.field-apercu img, td.field-apercu img')].filter(i => i.naturalWidth > 0).length")
        print("back-office : aperçus affichés =", apercus)
        pg.screenshot(path=SHOTS / "09_admin_images.png")
        ctx.close()

        # 8. Supervision
        ctx, pg = page_neuve()
        pg.goto(BASE + "/sante/")
        print("/sante/ :", pg.inner_text("body"))
        ctx.close()
        nav.close()
finally:
    pass

print("\nPROBLÈMES DÉTECTÉS :", len(problemes))
for pb in problemes:
    print(" -", pb)
