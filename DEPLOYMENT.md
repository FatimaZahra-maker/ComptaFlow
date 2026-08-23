# Déploiement ComptaFlow

## Préconditions

- fournir hors Git `DATABASE_URL`, `SECRET_KEY`, `POSTGRES_PASSWORD`,
  `CORS_ORIGINS` et `PUBLIC_API_URL` ;
- provisionner TLS et un reverse proxy en amont ;
- sauvegarder PostgreSQL et le volume documentaire avant toute migration ;
- confirmer que le plan comptable réel de chaque entreprise est importé.

## Procédure

1. Sauvegarder PostgreSQL avec `pg_dump` vers un stockage séparé et vérifier le fichier obtenu.
2. Sauvegarder le volume `comptaflow_storage` sans modifier les originaux.
3. Construire les images avec `docker compose -f docker-compose.prod.yml build`.
4. Vérifier la chaîne avec `alembic heads` puis exécuter la migration via le service `migrate`.
5. Démarrer API, worker et frontend, puis vérifier `/health` et `/ready`.
6. Exécuter un scénario synthétique complet avant d'ouvrir l'accès aux utilisateurs.

## Retour arrière

Revenir à l'image applicative précédente. Ne lancer un downgrade Alembic qu'après
analyse de la migration concernée. Si une restauration est indispensable, arrêter
les écritures applicatives puis restaurer la sauvegarde PostgreSQL et le stockage
documentaire correspondants dans un environnement contrôlé. Ne jamais tester cette
procédure sur la base réelle sans sauvegarde vérifiée.

## Limites externes

Le format Topaze réel, les règles fiscales particulières, le plan ANZOBAT et les
données d'immobilisations/stocks doivent être fournis et validés par le cabinet.
