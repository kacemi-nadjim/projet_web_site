"""
MIDDLEWARE.PY — En-têtes de sécurité ajoutés à chaque réponse.

Content-Security-Policy (CSP) : le navigateur n'exécute que les scripts
et ne charge que les ressources venant de notre propre domaine. Même si
un contenu malveillant parvenait à s'afficher dans une page, son script
serait bloqué (protection en profondeur contre les failles XSS).

Permissions-Policy : on coupe les API sensibles du navigateur dont le
site n'a pas besoin (caméra, micro, géolocalisation...).
"""

POLITIQUE_CSP = "; ".join([
    "default-src 'self'",
    "script-src 'self'",
    # Quelques attributs style="" existent dans les gabarits (largeur des
    # barres du dashboard) : on les autorise, sans autoriser aucun script.
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "base-uri 'self'",
    "object-src 'none'",
])

POLITIQUE_PERMISSIONS = "camera=(), microphone=(), geolocation=(), payment=(), usb=()"


class EnTetesSecuriteMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Le back-office Django utilise ses propres scripts en ligne :
        # on ne lui impose pas la CSP stricte (il reste protégé par login).
        if not request.path.startswith("/admin/"):
            response.setdefault("Content-Security-Policy", POLITIQUE_CSP)
        response.setdefault("Permissions-Policy", POLITIQUE_PERMISSIONS)
        return response
