# Règles permanentes — ComptaFlow

## Architecture

- Backend : FastAPI, SQLAlchemy, PostgreSQL, Alembic, Celery et Redis.
- Frontend : React, TypeScript et Vite.
- Environnement Conda : `comptaflow`.
- Travailler directement dans les vrais fichiers du dépôt.
- Préserver l’architecture existante sauf si une modification est réellement nécessaire et justifiée.

## Méthode de travail

- Avant toute modification, analyser l’architecture backend et frontend concernée.
- Lire les modèles SQLAlchemy, migrations Alembic, services, routes API, tests et fichiers frontend concernés.
- Vérifier les dépendances entre fichiers avant tout remplacement.
- Modifier le minimum de fichiers nécessaire.
- Ne supprimer aucune fonctionnalité existante fonctionnelle.
- Ne jamais modifier `.env`.
- Ne jamais afficher ou recopier de secret, clé API, mot de passe ou token.
- Ne jamais supprimer la base PostgreSQL.
- Ne jamais supprimer les volumes Docker.
- Ne jamais supprimer `storage_local`.
- Ne jamais exécuter `DROP DATABASE`, `DROP SCHEMA`, `docker volume rm`, `git reset --hard` ou `git clean -fd`.
- Ne pas créer de migration Alembic avant d’avoir vérifié toute la chaîne existante.
- Ne pas modifier une ancienne migration déjà appliquée en production ou dans la base locale sauf nécessité explicitement démontrée.
- Une nouvelle évolution de schéma doit normalement avoir une nouvelle migration.
- Après une modification, exécuter les validations backend et frontend pertinentes.
- Si un test échoue, rechercher la cause réelle, corriger le problème puis relancer les tests.
- Ne pas masquer un test qui échoue.
- Ne pas supprimer un test uniquement pour obtenir une suite verte.
- Ne pas utiliser de faux succès ou de mocks pour cacher un problème d’intégration réel.
- À la fin d’une tâche, fournir la liste exacte des fichiers créés et modifiés ainsi que les résultats des tests.

## Multi-tenant

- Toutes les données métier doivent être isolées par `cabinet_id`.
- Toutes les données comptables propres à une entreprise doivent aussi être isolées par `entreprise_id`.
- Toute lecture, écriture, mise à jour et suppression doit appliquer ces portées lorsqu’elles sont pertinentes.
- Une requête ne doit jamais pouvoir retourner les données d’un autre cabinet.
- Ne jamais utiliser uniquement un `id` métier lorsqu’un contrôle `cabinet_id` est également nécessaire.
- Les comptes comptables, écritures, mouvements bancaires, rapprochements et états doivent rester scoppés par entreprise.

## Entreprise / tiers

- Une entreprise gérée correspond au dossier comptable suivi par le cabinet.
- Un fournisseur ou un client externe est un tiers et ne doit pas être confondu avec une entreprise gérée.
- Achat :
  - entreprise gérée = destinataire ;
  - tiers = fournisseur.
- Vente :
  - entreprise gérée = émetteur ;
  - tiers = client.
- Un même tiers peut être fournisseur dans une opération et client dans une autre.
- Ne jamais décider Achat/Vente uniquement à partir du nom du tiers.

## Règles comptables et IA

- L’IA ne doit jamais inventer un numéro de compte comptable complet.
- L’IA peut déterminer une nature économique.
- Python applique les règles comptables.
- Le plan comptable propre à l’entreprise fournit le compte exact.
- Ne jamais inventer un compte pour équilibrer artificiellement une écriture.
- Si aucun compte exact ne peut être déterminé de façon sûre, mettre l’élément à vérifier.
- HT, TVA et TTC proviennent d’abord de l’extraction du document.
- Les calculs servent uniquement au contrôle de cohérence.
- Les calculs ne remplacent jamais silencieusement les valeurs extraites.
- Une incohérence HT + TVA ≠ TTC doit être signalée plutôt que corrigée automatiquement.
- Ne pas utiliser Gemini.
- Respecter le pipeline Groq, PaddleOCR et Ollama ainsi que les fallbacks existants.
- Un fallback ne doit pas introduire des règles différentes du pipeline principal.
- Les appels IA doivent conserver les données originales nécessaires à l’audit.

## Comptes comptables

- Les comptes exacts sont propres à chaque entreprise.
- Toujours respecter `cabinet_id + entreprise_id`.
- Pour les achats, le compte tiers doit être un compte fournisseur compatible.
- Pour les ventes, le compte tiers doit être un compte client compatible.
- Ne jamais choisir arbitrairement entre plusieurs comptes compatibles.
- Ne jamais créer un compte DIVERS pour HT ou TVA uniquement pour poursuivre automatiquement.
- Les comptes bancaires doivent provenir du plan comptable de l’entreprise.
- Si plusieurs comptes bancaires existent, utiliser RIB/IBAN ou une autre information fiable avant de sélectionner un compte.

## Banque

Préserver Banque V2 et notamment :

- rapprochement simple ;
- paiements partiels ;
- allocations multiples ;
- plusieurs règlements d’une facture ;
- plusieurs comptes bancaires ;
- RIB / IBAN ;
- acomptes ;
- frais bancaires ;
- virements internes ;
- `RapprochementBancaireAllocation`.

- Ne jamais affecter un règlement au-delà du montant restant dû.
- Ne jamais compter deux fois un virement interne.
- Toute allocation bancaire doit rester scoppée par cabinet et entreprise.

## Devises

- Préserver Bank Al-Maghrib V1.
- Conserver le montant original dans la devise du document.
- Conserver séparément le montant converti en MAD.
- Ne jamais écraser le montant original.
- Préserver toute la précision disponible du taux.
- Respecter l’unité de cotation.
- Si le cours correspondant à la date demandée est introuvable, signaler le problème.
- Ne jamais remplacer silencieusement le cours demandé par le cours du jour.

## Écritures comptables

Pour un achat :

Débit :

- compte HT charge ou immobilisation ;
- TVA récupérable si applicable.

Crédit :

- fournisseur.

Pour une vente :

Débit :

- client.

Crédit :

- produit HT ;
- TVA facturée si applicable.

Pour un règlement fournisseur :

Débit :

- fournisseur.

Crédit :

- banque.

Pour un règlement client :

Débit :

- banque.

Crédit :

- client.

- Toute écriture validée doit être équilibrée.
- Ne jamais ajouter une ligne fictive pour obtenir l’équilibre.

## Socle fonctionnel à préserver

- `CompteComptableEntreprise`
- `CompteBancaireEntreprise`
- `RapprochementBancaireAllocation`
- `MouvementBancaire`
- `EcritureComptable`
- Lignes Débit/Crédit
- Grand Livre
- Balance
- TVA comptable
- CPC
- Bilan
- Bank Al-Maghrib V1
- Banque V2
- Classification Achat / Vente / Banque
- Identification entreprise / tiers
- Chronos
- Gestion des doublons existante

## Alembic

Avant toute opération :

1. Vérifier les fichiers de `alembic/versions`.
2. Vérifier `revision`.
3. Vérifier `down_revision`.
4. Vérifier qu’il n’existe pas plusieurs heads inattendus.
5. Vérifier que les modèles SQLAlchemy peuvent être importés.

Commandes de diagnostic :

```powershell
alembic heads
alembic current
alembic history
```
