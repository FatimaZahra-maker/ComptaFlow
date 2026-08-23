# ComptaFlow — VERSION CONSOLIDÉE ACTUELLE

Cette archive regroupe en un seul projet propre tout ce qui a réellement été
codé et consolidé jusqu'à **Banque V2**.

## Inclus

- Classification Documents / Achat / Vente / Banque
- Identification entreprise / tiers
- Chronos et gestion des doublons existante
- Upload multiple séquentiel
- Prétraitement / orientation déjà présent dans le projet de base
- Moteur comptable Achat
- Moteur comptable Vente
- TVA achat
- Plan comptable par entreprise
- Banque V1 + rapprochement
- Devises Bank Al-Maghrib V1
- Lignes Débit / Crédit
- Grand Livre
- Balance
- TVA comptable
- CPC V1
- Bilan V1
- Banque V2 :
  - allocations partielles / multiples
  - comptes bancaires entreprise
  - RIB / IBAN
  - rapprochement bancaire avancé prévu par la V2
- Correctif CompteComptableEntreprise
- Migration manquante c4f8a2d9e310 restaurée
- Modèle EcritureComptable consolidé avec :
  - compte_tiers
  - compte_tva
  - compte_ht
  - libelle

## Migration Alembic finale disponible

c8a1d2e3f470 (head)

Chaîne récente :
b91f2d7c4a80
-> c4f8a2d9e310
-> d7e3a1f6b420
-> f1a6c9e4d230
-> g3b8d2f5c640
-> h4c9e6a7d510
-> c8a1d2e3f470

## IMPORTANT : ce qui n'est PAS encore développé

Cette archive ne prétend pas être la version métier finale de production.
Les blocs suivants restent à développer après cette consolidation :

- Devises V2 : gain/perte de change au règlement
- TVA fiscale V2 complète
- Ecritures de clôture avancées
- CPC/Bilan V2
- Contrôles globaux de clôture (patch volontairement reporté)
- Email automatique
- Nouvelle UX de sélection entreprise
- Import massif / digitalisation finale des entreprises
- Sécurité production finale / durcissement
- ESG

## Secrets et données

L'archive ne contient volontairement PAS :
- backend/.env
- les fichiers de backend/storage_local
- .git
- node_modules
- __pycache__
- .pytest_cache

Ne remplace pas ton .env par un fichier venant d'ailleurs.
Garde ton .env actuel.

## Installation recommandée

1. Garde une sauvegarde de ton projet actuel.
2. Décompresse cette archive dans un NOUVEAU dossier.
3. Copie uniquement ton fichier existant :
   backend/.env
   depuis l'ancien projet vers le nouveau.
4. Si tu veux conserver les anciens documents locaux, copie aussi le contenu de :
   backend/storage_local
   depuis l'ancien projet vers le nouveau.
5. Ne supprime PAS PostgreSQL, Redis ni les volumes Docker.

## Backend

PowerShell :

cd C:\Users\HP\Desktop\ComptaFlow_vs_FINAL\backend
conda activate comptaflow

python -m compileall app alembic tests

alembic heads
# attendu :
# c8a1d2e3f470 (head)

alembic current
# si Banque V2 n'a pas encore été appliquée, il est normal de voir
# h4c9e6a7d510 ou une révision précédente.

alembic upgrade head

alembic current
# attendu après migration :
# c8a1d2e3f470 (head)

python -m pytest -q

## Frontend

cd C:\Users\HP\Desktop\ComptaFlow_vs_FINAL\frontend

npm ci

npx tsc -p tsconfig.app.json --noEmit --noUnusedLocals false --noUnusedParameters false

npm run dev

## Lancer le backend

Terminal 1 :

cd C:\Users\HP\Desktop\ComptaFlow_vs_FINAL\backend
conda activate comptaflow
uvicorn app.main:app --reload

Terminal 2 :

cd C:\Users\HP\Desktop\ComptaFlow_vs_FINAL\backend
conda activate comptaflow
celery -A app.core.celery_app.celery_app worker --loglevel=info --pool=solo

## Validation réalisée avant création de cette archive

Sur la reconstruction consolidée :

- python -m compileall -q app alembic tests : OK
- alembic heads : c8a1d2e3f470 (head)
- import des modèles sous SQLite : OK
- pytest avec environnement SQLite de test : 72 passed
- TypeScript : OK

Les tests PostgreSQL réels et les appels externes (Groq/BAM/Ollama) doivent être
validés dans ton environnement local.
