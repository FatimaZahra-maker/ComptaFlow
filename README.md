# ComptaFlow

Plateforme intelligente de gestion documentaire et de pré-comptabilité destinée aux cabinets comptables.

Technologies :

- React
- TypeScript
- FastAPI
- PostgreSQL
- PaddleOCR
- Ollama
- Docker

## Fonctionnalités administratives et Assistant

- **Historique** : `/admin/historique`, réservé aux rôles `ADMIN_CABINET` et
  `SUPER_ADMIN`, avec filtrage strict par cabinet côté API.
- **Assistant ComptaFlow** : `/assistant`, en lecture seule, avec recherches
  SQLAlchemy contrôlées et ouverture authentifiée des pièces originales.

Les détails de sécurité, les endpoints et le scénario de validation sont
décrits dans [HISTORIQUE_ASSISTANT.md](HISTORIQUE_ASSISTANT.md).
