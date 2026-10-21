// Vérification de compatibilité multi-navigateurs du CSS de PixBank.
// Utilisation (Node.js requis) : npm install   puis   npm run verifier
// Pour chaque propriété CSS de static/css/style.css, l'outil doiuse consulte
// la base « Can I use » et signale celles qu'un des navigateurs ciblés ne gère pas.
import fs from "fs";
import postcss from "postcss";
import doiuse from "doiuse";
const css = fs.readFileSync(process.argv[2], "utf8");
const navigateurs = ["last 2 Chrome versions", "last 2 Firefox versions", "last 2 Safari versions",
  "last 2 Edge versions", "last 2 iOS versions", "last 2 ChromeAndroid versions", "Firefox ESR"];
const out = [];
await postcss([doiuse({ browsers: navigateurs, onFeatureUsage: (u) => out.push(u.message) })]).process(css, { from: undefined });
console.log("Navigateurs :", navigateurs.join(", "));
console.log(out.length ? out.join("\n") : "Aucune propriété CSS non prise en charge.");
