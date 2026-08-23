"""
app/schemas/entreprise.py

Schémas Pydantic utilisés par l'API des entreprises.

Une entreprise correspond ici à une société dont le cabinet
gère réellement la comptabilité.

Pour commencer, seul le nom est obligatoire lors de la création.
"""

import uuid

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
)


# ============================================================
# CRÉATION
# ============================================================

class EntrepriseCreate(BaseModel):
    """
    Données nécessaires pour ajouter une entreprise suivie.

    Exemple :
        {
            "nom": "ANZOBAT"
        }
    """

    nom: str = Field(
        min_length=2,
        max_length=255,
    )

    @field_validator("nom")
    @classmethod
    def nettoyer_nom(
        cls,
        valeur: str,
    ) -> str:
        """
        Nettoie les espaces inutiles.

        Exemple :
            "   ANZOBAT   SARL   "
        devient :
            "ANZOBAT SARL"
        """

        nom = " ".join(
            valeur.strip().split()
        )

        if len(nom) < 2:
            raise ValueError(
                "Le nom de l'entreprise est trop court."
            )

        return nom


# ============================================================
# RÉPONSE API
# ============================================================

class EntrepriseOut(BaseModel):
    """
    Format retourné au frontend.
    """

    model_config = ConfigDict(
        from_attributes=True
    )

    id: uuid.UUID
    nom: str

    ice: str | None = None

    creee_automatiquement: bool = False