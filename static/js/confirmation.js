/* Confirmation avant une action irréversible (suppression d'une image).
   Tout formulaire portant l'attribut data-confirmation affiche ce message
   avant l'envoi. Script placé dans un fichier séparé : la politique de
   sécurité CSP du site interdit tout script écrit dans la page. */
document.addEventListener('submit', function (evenement) {
    var message = evenement.target.getAttribute('data-confirmation');
    if (message && !window.confirm(message)) {
        evenement.preventDefault();
    }
});
