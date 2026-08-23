"""
app/api/entreprises.py

API de gestion des entreprises de ComptaFlow.

CORRECTION :
- Les entreprises déjà présentes dans la base restent visibles.
- On ne filtre PLUS sur creee_automatiquement=False.
- Le placeholder système "Entreprise à identifier" n'est pas affiché
  dans la liste normale.
- Une nouvelle entreprise peut être ajoutée avec son nom seulement.
"""

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    status,
)

from sqlalchemy import (
    func,
    select,
)

from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user

from app.models.entreprise import Entreprise
from app.models.user import User

from app.schemas.entreprise import (
    EntrepriseCreate,
    EntrepriseOut,
)


router = APIRouter(
    prefix="/entreprises",
    tags=["entreprises"],
)


NOM_ENTREPRISE_A_IDENTIFIER = "Entreprise à identifier"


# ============================================================
# OUTILS
# ============================================================

def _normaliser_nom_simple(
    nom: str,
) -> str:
    """
    Nettoie un nom saisi manuellement.

    Exemple :
        "   ANZOBAT   SARL   "
    devient :
        "ANZOBAT SARL"
    """

    return " ".join(
        nom.strip().split()
    )


# ============================================================
# LISTE DES ENTREPRISES
# ============================================================

@router.get(
    "",
    response_model=list[EntrepriseOut],
)
def list_entreprises(
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Retourne toutes les entreprises actives du cabinet.

    IMPORTANT :
    on ne masque PAS les anciennes entreprises simplement
    parce qu'elles ont été créées automatiquement.

    On exclut seulement le placeholder système :
        "Entreprise à identifier"
    """

    query = (
        select(
            Entreprise
        )
        .where(
            Entreprise.cabinet_id
            == current_user.cabinet_id,

            Entreprise.is_active.is_(
                True
            ),

            func.lower(
                func.trim(
                    Entreprise.nom
                )
            )
            != NOM_ENTREPRISE_A_IDENTIFIER.lower(),
        )
        .order_by(
            Entreprise.nom.asc()
        )
    )

    entreprises = (
        db.execute(
            query
        )
        .scalars()
        .all()
    )

    return entreprises


# ============================================================
# AJOUT D'UNE ENTREPRISE
# ============================================================

@router.post(
    "",
    response_model=EntrepriseOut,
    status_code=status.HTTP_201_CREATED,
)
def create_entreprise(
    payload: EntrepriseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(
        get_current_user
    ),
):
    """
    Ajoute une entreprise au cabinet.

    Pour l'instant :
        seul le nom est obligatoire.

    Exemple :
        ANZOBAT

    Si cette entreprise existe déjà dans la base parce qu'elle
    avait été détectée automatiquement auparavant, on réutilise
    cette ligne au lieu de créer un doublon.
    """

    nom = _normaliser_nom_simple(
        payload.nom
    )


    # ========================================================
    # NOM RÉSERVÉ
    # ========================================================

    if (
        nom.casefold()
        == NOM_ENTREPRISE_A_IDENTIFIER.casefold()
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Le nom « Entreprise à identifier » "
                "est réservé au système."
            ),
        )


    # ========================================================
    # CHERCHER LE MÊME NOM
    # ========================================================

    query = (
        select(
            Entreprise
        )
        .where(
            Entreprise.cabinet_id
            == current_user.cabinet_id,

            func.lower(
                func.trim(
                    Entreprise.nom
                )
            )
            == nom.lower(),
        )
        .order_by(
            Entreprise.created_at.asc()
        )
    )


    existantes = (
        db.execute(
            query
        )
        .scalars()
        .all()
    )


    # ========================================================
    # ENTREPRISE DÉJÀ EXISTANTE
    # ========================================================

    if existantes:

        entreprise = existantes[0]


        # ----------------------------------------------------
        # ELLE EXISTAIT MAIS ÉTAIT DÉSACTIVÉE
        # ----------------------------------------------------

        if not entreprise.is_active:

            entreprise.is_active = True


        # ----------------------------------------------------
        # ELLE AVAIT ÉTÉ CRÉÉE AUTOMATIQUEMENT
        # ----------------------------------------------------
        #
        # Maintenant que l'utilisateur l'ajoute volontairement,
        # on considère qu'elle a été confirmée manuellement.

        if entreprise.creee_automatiquement:

            entreprise.creee_automatiquement = False

            entreprise.nom = nom

            db.commit()

            db.refresh(
                entreprise
            )

            return entreprise


        # ----------------------------------------------------
        # ELLE EXISTE DÉJÀ NORMALEMENT
        # ----------------------------------------------------

        if entreprise.is_active:

            db.commit()

            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=(
                    f"L'entreprise « {entreprise.nom} » "
                    "existe déjà."
                ),
            )


    # ========================================================
    # CRÉATION
    # ========================================================

    entreprise = Entreprise(
        cabinet_id=current_user.cabinet_id,

        nom=nom,

        ice=None,

        identifiant_fiscal=None,

        rc=None,

        is_active=True,

        # False = ajout volontaire depuis l'interface
        creee_automatiquement=False,
    )


    db.add(
        entreprise
    )

    db.commit()

    db.refresh(
        entreprise
    )


    return entreprise