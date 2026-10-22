"""
ECOINDEX.PY — Calcul de l'EcoIndex d'une page web.

Méthode officielle de l'association GreenIT / collectif Conception
Numérique Responsable (cnumr) : https://www.ecoindex.fr/comment-ca-marche/
La note (0 à 100, grade A à G) combine trois mesures de la page :
  - le nombre d'éléments du DOM (complexité de la page),   poids 3
  - le nombre de requêtes HTTP,                             poids 2
  - le poids total transféré (Ko),                          poids 1
Chaque mesure est positionnée sur une échelle de quantiles établie sur
un large échantillon de sites réels.

Quantiles et grades : référentiel « ecoindex_reference » V1.2 (cnumr),
repris à l'identique (licence CC BY-NC-ND 3.0, usage non commercial).
"""

QUANTILES = {
    "dom": [0, 47, 75, 159, 233, 298, 358, 417, 476, 537, 603, 674, 753, 843,
            949, 1076, 1237, 1459, 1801, 2479, 594601],
    "req": [0, 2, 15, 25, 34, 42, 49, 56, 63, 70, 78, 86, 95, 105, 117, 130,
            147, 170, 205, 281, 3920],
    "size": [0, 1.37, 144.7, 319.53, 479.46, 631.97, 783.38, 937.91, 1098.62,
             1265.47, 1448.32, 1648.27, 1876.08, 2142.06, 2465.37, 2866.31,
             3401.59, 4155.73, 5400.08, 8037.54, 223212.26],
}
GRADES = [(80, "A"), (70, "B"), (55, "C"), (40, "D"), (25, "E"), (10, "F"), (0, "G")]


def _quantile(echelle, valeur):
    for i in range(1, len(echelle)):
        if valeur < echelle[i]:
            return i - 1 + (valeur - echelle[i - 1]) / (echelle[i] - echelle[i - 1])
    return len(echelle) - 1


def ecoindex(nb_dom, nb_requetes, poids_ko):
    """Retourne (score sur 100, grade A-G, gaz à effet de serre gCO2e, eau cl)."""
    score = 100 - 5 * (3 * _quantile(QUANTILES["dom"], nb_dom)
                       + 2 * _quantile(QUANTILES["req"], nb_requetes)
                       + _quantile(QUANTILES["size"], poids_ko)) / 6
    grade = next((g for seuil, g in GRADES if score > seuil), "G")
    ges = 2 + 2 * (50 - score) / 100          # gCO2e par visite (formule EcoIndex)
    eau = 3 + 3 * (50 - score) / 100          # centilitres par visite
    return round(score, 1), grade, round(ges, 2), round(eau, 2)
