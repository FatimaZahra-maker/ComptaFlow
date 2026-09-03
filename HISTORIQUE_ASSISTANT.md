# Historique et Assistant ComptaFlow

## Mise en route

```powershell
conda activate comptaflow
cd backend
alembic upgrade head
uvicorn app.main:app --reload
```

Dans un second terminal :

```powershell
cd frontend
npm install
npm run dev
```

La migration `d2a7f1c8e950` étend la table `audit_logs` existante. Elle ne crée
pas un second journal et conserve la colonne historique `details`.

## Historique

La page `/admin/historique` et les endpoints `GET /audit`,
`GET /audit/options` et `GET /audit/{event_id}` sont réservés à
`ADMIN_CABINET` et `SUPER_ADMIN`. Le backend impose toujours le `cabinet_id`
issu du JWT. Il n'existe aucune route de modification ou suppression d'un
événement.

Les filtres disponibles sont la période, l'utilisateur, le rôle, l'entreprise,
le module, l'action, la ressource, le statut et la recherche textuelle. Les
snapshots avant/après sont nettoyés par le service central : mots de passe,
tokens, clés, cookies et texte OCR complet sont refusés.

## Assistant

L'endpoint `POST /assistant/query` accepte une question, un contexte document
optionnel et un contexte entreprise optionnel. Le cabinet n'est jamais accepté
depuis le client : il est toujours extrait de l'utilisateur authentifié.

L'assistant sait notamment :

- lister ou compter les entreprises actives accessibles dans le cabinet,
  y compris avec des formulations françaises approximatives ;
- rechercher une facture par numéro, entreprise, date de facture, date
  d'importation ou montant TTC ;
- afficher les champs extraits autorisés ;
- ouvrir la fiche et le fichier original via `GET /documents/{id}/fichier` ;
- retrouver les allocations et paiements partiels ;
- calculer les totaux TVA via le moteur comptable existant ;
- lister les factures non réglées, les écritures validées non saisies dans
  Topaze et les tâches en retard ;
- interroger l'historique d'une facture pour les administrateurs seulement.

Le LLM ne reçoit jamais de connexion ou de requête SQL. Les intentions sont
validées contre une liste blanche et toutes les lectures utilisent des requêtes
SQLAlchemy déterministes scoppées par cabinet et entreprise. Les demandes SQL,
de mots de passe ou de contournement des cabinets sont refusées.

Le bouton circulaire disponible sur toutes les pages authentifiées ouvre la
même conversation dans un panneau flottant. Sa position peut être modifiée à
la souris ou au toucher et est mémorisée par utilisateur. La page
`/assistant` et ce panneau réutilisent le même état et les mêmes composants.

## Vérification manuelle

1. importer plusieurs factures pour une entreprise ;
2. modifier, valider et marquer l'une d'elles comme saisie dans Topaze ;
3. se connecter comme administrateur et ouvrir `/admin/historique` ;
4. filtrer sur l'utilisateur et ouvrir le détail avant/après ;
5. ouvrir `/assistant` et sélectionner l'entreprise ;
6. demander `Donne-moi la facture ANZOBAT du 12/12/2026` ;
7. ouvrir la pièce avec le bouton sécurisé ;
8. demander `Affiche ses données extraites`, puis `Quel règlement lui correspond ?` ;
9. comme administrateur, demander `Qui a modifié cette facture ?` ;
10. vérifier avec un rôle non administrateur que la dernière question retourne
   `403` et que le menu Historique n'est pas affiché.
11. depuis une autre page, déplacer le bouton de l'Assistant puis recharger la
    page pour vérifier que sa position est conservée ;
12. demander `quelle sont les entreprise existe ?`, ouvrir les documents d'une
    entreprise et vérifier que le chrono est filtré ;
13. réduire puis rouvrir le panneau et vérifier que les messages sont conservés.

## Validation automatisée

```powershell
cd backend
python -m pytest -q
alembic check

cd ..\frontend
npm test
npm run typecheck
npm run build
npm run lint
```
