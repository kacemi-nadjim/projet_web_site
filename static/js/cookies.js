/* Bandeau d'information cookies (RGPD).
   Placé dans un fichier séparé (et non dans la page) pour que la
   politique de sécurité CSP puisse interdire tout script en ligne. */
(function () {
    var b = document.getElementById('cookie-banner');
    if (!b) { return; }
    if (document.cookie.indexOf('cookie_ok=1') !== -1) { b.style.display = 'none'; return; }
    document.getElementById('cookie-ok').addEventListener('click', function () {
        document.cookie = 'cookie_ok=1; max-age=31536000; path=/; SameSite=Lax; Secure';
        b.style.display = 'none';
    });
})();
