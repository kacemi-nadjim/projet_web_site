-- ============================================================
-- PixBank — Création de la base PostgreSQL de production
-- À exécuter UNE fois par l'administrateur de la base (psql).
-- Principe du MOINDRE PRIVILÈGE : l'application se connecte avec un
-- compte qui ne peut agir que sur SA base, sans droit d'administration.
-- ============================================================

-- 1. Compte applicatif (mot de passe long et aléatoire, stocké uniquement
--    dans la variable d'environnement DATABASE_URL du serveur)
CREATE ROLE pixbank_app LOGIN PASSWORD 'REMPLACER_PAR_UN_MOT_DE_PASSE_ALEATOIRE'
    NOSUPERUSER NOCREATEDB NOCREATEROLE;

-- 2. Base dédiée, encodage UTF-8 (accents des noms de catégories)
CREATE DATABASE pixbank OWNER pixbank_app ENCODING 'UTF8' TEMPLATE template0;

-- 3. Personne d'autre ne peut se connecter à cette base
REVOKE ALL ON DATABASE pixbank FROM PUBLIC;
GRANT CONNECT ON DATABASE pixbank TO pixbank_app;

-- 4. Côté serveur : n'accepter que les connexions chiffrées (pg_hba.conf)
--    hostssl  pixbank  pixbank_app  <ip_du_serveur_web>/32  scram-sha-256

-- Puis, sur le serveur web :
--   export DATABASE_URL="postgres://pixbank_app:<mot_de_passe>@<hote>:5432/pixbank?sslmode=require"
--   python manage.py migrate
