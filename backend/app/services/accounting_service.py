"""
app/services/accounting_service.py

Transformation automatique des données extraites
en écritures comptables.

Règle importante du Journal d'Achat :

- HT / TVA / TTC viennent de l'extraction ;
- ils ne sont PAS recalculés pour remplacer les données ;
- Python vérifie seulement leur cohérence ;
- le libellé est automatique :
      FOURNISSEUR + NUMERO FACTURE
- le compte fournisseur déjà connu est réutilisé ;
- si aucun compte individuel n'est encore connu,
  on utilise provisoirement FRS DIVERS.

Le moteur ACHAT ajoute maintenant une règle contrôlée de nature comptable :
- l'IA propose seulement une nature économique parmi une liste fermée ;
- Python associe cette nature à une famille CGNC ;
- aucun numéro Topaze complet n'est inventé ;
- si un compte exact déjà confirmé existe pour la même nature dans la même
  entreprise, il est réutilisé ;
- sinon la famille CGNC est mémorisée dans donnees_extraites et l'écriture
  reste À VÉRIFIER jusqu'à configuration du compte exact.

Le moteur TVA ACHAT est également déterministe :
- aucune TVA n'est recalculée ;
- une charge utilise la famille TVA récupérable sur charges ;
- une immobilisation confirmée utilise la famille TVA récupérable sur immobilisations ;
- une immobilisation seulement candidate reste À VÉRIFIER ;
- aucun numéro Topaze complet n'est inventé.
"""

from __future__ import annotations

import unicodedata

from datetime import date as date_type

from decimal import (
    Decimal,
    ROUND_HALF_UP,
)

from sqlalchemy.orm import Session

from app.models.document import Document

from app.models.ecriture import (
    EcritureComptable,
)

from app.models.enums import (
    StatutValidationEnum,
    TauxTVAEnum,
    TypeEcritureEnum,
)

from app.models.mouvement_bancaire import (
    MouvementBancaire,
)

from app.services.accounting_rules_service import (
    FAMILLE_TVA_FACTUREE,
    FAMILLE_TVA_RECUPERABLE_CHARGES,
    FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS,
    compte_correspond_a_famille,
    normaliser_nature_comptable,
    normaliser_nature_vente,
    normaliser_traitement_comptable_confirme,
    obtenir_famille_tva_achat,
    obtenir_famille_tva_vente,
    obtenir_regle_achat,
    obtenir_regle_vente,
)

from app.services import exchange_rate_service
from app.services import plan_comptable_service
from app.services import rapprochement_bancaire_service
from app.services import ligne_comptable_service
from app.services import workflow_comptable_service


# ============================================================
# COMPTES DIVERS
# ============================================================

# Compte fournisseur DIVERS vu dans le plan transmis.
COMPTE_FOURNISSEUR_DIVERS = "441100000000"

# Même principe côté clients.
COMPTE_CLIENT_DIVERS = "342100000000"


_TAUX_VALIDES = {
    20: TauxTVAEnum.TAUX_20,
    14: TauxTVAEnum.TAUX_14,
    10: TauxTVAEnum.TAUX_10,
    7: TauxTVAEnum.TAUX_7,
    0: TauxTVAEnum.TAUX_0,
}


# ============================================================
# NORMALISATION
# ============================================================

def _normaliser_categorie(
    categorie: object | None,
) -> str:

    if categorie is None:
        return ""

    raw_value = getattr(
        categorie,
        "value",
        categorie,
    )

    text = str(
        raw_value
    ).strip().lower()

    text = "".join(
        char
        for char in unicodedata.normalize(
            "NFKD",
            text,
        )
        if not unicodedata.combining(
            char
        )
    )

    return (
        text
        .replace(
            "-",
            "_",
        )
        .replace(
            " ",
            "_",
        )
    )


def _normaliser_nom_tiers(
    valeur: object | None,
) -> str:

    if valeur is None:
        return ""

    text = str(
        valeur
    ).strip().upper()

    text = "".join(
        char
        for char in unicodedata.normalize(
            "NFKD",
            text,
        )
        if not unicodedata.combining(
            char
        )
    )

    return " ".join(
        text.split()
    )


# ============================================================
# TYPE ÉCRITURE
# ============================================================

def _determiner_type_ecriture(
    categorie: object | None,
) -> TypeEcritureEnum:

    normalized = (
        _normaliser_categorie(
            categorie
        )
    )

    mapping = {
        "achat":
            TypeEcritureEnum.ACHAT,

        "achats":
            TypeEcritureEnum.ACHAT,

        "facture_achat":
            TypeEcritureEnum.ACHAT,

        "factures_achat":
            TypeEcritureEnum.ACHAT,

        "fournisseur":
            TypeEcritureEnum.ACHAT,

        "fournisseurs":
            TypeEcritureEnum.ACHAT,

        "vente":
            TypeEcritureEnum.VENTE,

        "ventes":
            TypeEcritureEnum.VENTE,

        "facture_vente":
            TypeEcritureEnum.VENTE,

        "factures_vente":
            TypeEcritureEnum.VENTE,

        "client":
            TypeEcritureEnum.VENTE,

        "clients":
            TypeEcritureEnum.VENTE,

        "banque":
            TypeEcritureEnum.BANQUE,

        "releve_bancaire":
            TypeEcritureEnum.BANQUE,

        "cnss":
            TypeEcritureEnum.CNSS,

        "tva":
            TypeEcritureEnum.IMPOT,

        "impot":
            TypeEcritureEnum.IMPOT,

        "impots":
            TypeEcritureEnum.IMPOT,
    }

    return mapping.get(
        normalized,
        TypeEcritureEnum.AUTRE,
    )


# ============================================================
# TVA
# ============================================================

def _normaliser_taux_tva(
    valeur: object | None,
) -> TauxTVAEnum | None:
    """
    Conserve le taux extrait lorsqu'il correspond
    à un taux reconnu.
    """

    if valeur is None:
        return None

    try:
        entier = int(
            round(
                float(
                    valeur
                )
            )
        )

    except (
        TypeError,
        ValueError,
    ):
        return None

    return _TAUX_VALIDES.get(
        entier
    )


# ============================================================
# MONTANTS
# ============================================================

def _vers_decimal(
    valeur: object | None,
) -> Decimal | None:

    if valeur is None:
        return None

    try:
        return Decimal(
            str(
                valeur
            )
        ).quantize(
            Decimal(
                "0.01"
            ),
            rounding=ROUND_HALF_UP,
        )

    except Exception:
        return None


def _lire_montants_et_controler(
    donnees: dict,
) -> tuple[
    Decimal | None,
    Decimal | None,
    Decimal,
    bool,
    str | None,
]:
    """
    IMPORTANT :

    HT / TVA / TTC sont LUS depuis l'extraction.

    Ils ne sont pas recalculés afin de remplacer
    les valeurs de la facture.

    On fait uniquement :

        HT + TVA ≈ TTC

    pour vérifier la cohérence.
    """

    ht = _vers_decimal(
        donnees.get(
            "montant_ht"
        )
    )

    tva = _vers_decimal(
        donnees.get(
            "montant_tva"
        )
    )

    ttc = _vers_decimal(
        donnees.get(
            "montant_ttc"
        )
    )

    # TTC est obligatoire dans l'ancien modèle SQL.
    if ttc is None:

        return (
            ht,
            tva,
            Decimal(
                "0.00"
            ),
            True,
            (
                "Montant TTC absent "
                "de l'extraction."
            ),
        )

    # Vérification seulement.
    if (
        ht is not None
        and tva is not None
    ):

        ecart = abs(
            (
                ht
                + tva
            )
            - ttc
        )

        if (
            ecart
            > Decimal(
                "1.00"
            )
        ):

            return (
                ht,
                tva,
                ttc,
                True,
                (
                    "Contrôle montants échoué : "
                    f"HT ({ht}) + TVA ({tva}) "
                    f"!= TTC ({ttc})."
                ),
            )

    return (
        ht,
        tva,
        ttc,
        False,
        None,
    )


# ============================================================
# LIBELLÉ
# ============================================================

def _construire_libelle(
    tiers: object | None,
    numero_piece: object | None,
) -> str | None:

    parties = [
        str(
            valeur
        ).strip()

        for valeur in (
            tiers,
            numero_piece,
        )

        if (
            valeur is not None
            and str(
                valeur
            ).strip()
        )
    ]

    return (
        " ".join(
            parties
        )
        or None
    )


# ============================================================
# COMPTE TIERS
# ============================================================

def _compte_tiers_divers(
    type_ecriture: TypeEcritureEnum,
) -> str | None:

    if (
        type_ecriture
        == TypeEcritureEnum.ACHAT
    ):

        return (
            COMPTE_FOURNISSEUR_DIVERS
        )

    if (
        type_ecriture
        == TypeEcritureEnum.VENTE
    ):

        return (
            COMPTE_CLIENT_DIVERS
        )

    return None


def _choisir_compte_tiers(
    *,
    type_ecriture: TypeEcritureEnum,
    compte_existant: str | None,
    compte_plan: str | None,
    compte_fourni: str | None,
    compte_historique: str | None,
    compte_divers_plan: str | None,
) -> tuple[str | None, str | None]:
    """Choisit le compte tiers sans figer un ancien fallback DIVERS.

    Un compte DIVERS déjà stocké reste un fallback, pas une correction
    humaine. Il ne doit donc jamais empêcher un compte tiers exact, ajouté
    ultérieurement au plan de l'entreprise, d'être résolu.
    """
    fallback_provisoire = _compte_tiers_divers(type_ecriture)
    comptes_divers = {
        compte
        for compte in (fallback_provisoire, compte_divers_plan)
        if compte
    }
    existant_confirme = (
        compte_existant
        if compte_existant not in comptes_divers
        else None
    )

    if existant_confirme:
        return existant_confirme, "deja_confirme"
    if compte_plan:
        return compte_plan, "plan_comptable_entreprise"
    if compte_fourni and compte_fourni not in comptes_divers:
        return compte_fourni, "donnee_confirmee"
    if compte_historique:
        return compte_historique, "historique_entreprise"
    if compte_divers_plan:
        return compte_divers_plan, "divers_plan_entreprise"
    if fallback_provisoire:
        return fallback_provisoire, "divers_provisoire"
    return None, None


def _chercher_compte_tiers_connu(
    db: Session,
    document: Document,
    type_ecriture: TypeEcritureEnum,
    tiers: str | None,
) -> str | None:
    """
    Réutilise automatiquement un compte déjà connu
    pour le même fournisseur/client dans la même
    entreprise.

    Exemple :

        ANZOBAT
        TUNARUZ
        441103000000

    Nouvelle facture TUNARUZ
        ↓
    441103000000 automatiquement.
    """

    if (
        document.entreprise_id
        is None
        or not tiers
    ):
        return None

    nom_normalise = (
        _normaliser_nom_tiers(
            tiers
        )
    )

    if not nom_normalise:
        return None

    candidates = (
        db.query(
            EcritureComptable
        )
        .filter(
            EcritureComptable.cabinet_id
            == document.cabinet_id,

            EcritureComptable.entreprise_id
            == document.entreprise_id,

            EcritureComptable.type_ecriture
            == type_ecriture,

            EcritureComptable.compte_tiers
            .isnot(
                None
            ),

            EcritureComptable.document_id
            != document.id,
        )
        .order_by(
            EcritureComptable
            .created_at
            .desc()
        )
        .all()
    )

    compte_divers = (
        _compte_tiers_divers(
            type_ecriture
        )
    )

    for candidate in candidates:

        if (
            _normaliser_nom_tiers(
                candidate.tiers
            )
            != nom_normalise
        ):
            continue

        compte = (
            candidate.compte_tiers
            or ""
        ).strip()

        # Ne pas apprendre "DIVERS" comme
        # compte personnel du fournisseur.
        if (
            compte
            and compte
            != compte_divers
            and _compte_tiers_est_compatible(
                compte,
                type_ecriture,
            )
        ):
            return compte

    return None


# ============================================================
# VALIDATION FAMILLE COMPTE TIERS
# ============================================================

def _compte_tiers_est_compatible(
    compte: object | None,
    type_ecriture: TypeEcritureEnum,
) -> bool:
    """
    Un achat doit utiliser une famille fournisseur 44...
    Une vente doit utiliser une famille client 34...

    Les autres types d'écriture ne sont pas concernés.
    """

    if compte is None:
        return False

    propre = "".join(
        caractere
        for caractere in str(compte).strip()
        if caractere.isdigit()
    )

    if not propre:
        return False

    if type_ecriture == TypeEcritureEnum.ACHAT:
        return propre.startswith("44")

    if type_ecriture == TypeEcritureEnum.VENTE:
        return propre.startswith("34")

    return True


# ============================================================
# COMPTE HT ACHAT
# ============================================================

def _chercher_compte_ht_connu(
    db: Session,
    document: Document,
    nature_comptable: str,
    famille_cgnc: str,
) -> str | None:
    """
    Cherche un compte HT déjà confirmé pour la même nature
    dans la même entreprise.

    On ne se base jamais uniquement sur le nom du fournisseur :
    un même fournisseur peut facturer des natures différentes.
    """

    if document.entreprise_id is None:
        return None

    candidates = (
        db.query(EcritureComptable)
        .filter(
            EcritureComptable.cabinet_id == document.cabinet_id,
            EcritureComptable.entreprise_id == document.entreprise_id,
            EcritureComptable.type_ecriture == TypeEcritureEnum.ACHAT,
            EcritureComptable.compte_ht.isnot(None),
            EcritureComptable.document_id != document.id,
        )
        .order_by(EcritureComptable.created_at.desc())
        .all()
    )

    for candidate in candidates:
        compte = (candidate.compte_ht or "").strip()

        if not compte_correspond_a_famille(
            compte,
            famille_cgnc,
        ):
            continue

        candidate_document = getattr(candidate, "document", None)
        candidate_donnees = (
            dict(candidate_document.donnees_extraites or {})
            if candidate_document is not None
            else {}
        )

        candidate_nature = normaliser_nature_comptable(
            candidate_donnees.get("nature_comptable")
        )

        if candidate_nature == nature_comptable:
            return compte

    return None


def _resoudre_compte_ht_achat(
    db: Session,
    document: Document,
    ecriture: EcritureComptable,
    donnees: dict,
) -> tuple[str | None, list[str]]:
    """Résout le compte HT ACHAT avec priorité au plan de l'entreprise."""
    raisons: list[str] = []

    nature = normaliser_nature_comptable(
        donnees.get("nature_comptable")
    )
    donnees["nature_comptable"] = nature

    if nature is None:
        donnees["famille_compte_ht_suggeree"] = None
        donnees["libelle_compte_ht_suggere"] = None
        donnees["traitement_comptable_suggere"] = None
        donnees["compte_ht_resolution"] = "nature_manquante"
        raisons.append(
            "Nature comptable de l'achat non déterminée : "
            "compte HT non affecté."
        )
        return ecriture.compte_ht, raisons

    regle = obtenir_regle_achat(nature)
    if regle is None:
        donnees["compte_ht_resolution"] = "nature_non_supportee"
        raisons.append(f"Nature comptable non supportée : {nature}.")
        return ecriture.compte_ht, raisons

    donnees["famille_compte_ht_suggeree"] = regle.famille_cgnc
    donnees["libelle_compte_ht_suggere"] = regle.libelle
    donnees["traitement_comptable_suggere"] = regle.traitement

    # 1. Une correction déjà présente sur l'écriture courante reste prioritaire.
    if ecriture.compte_ht:
        donnees["compte_ht_resolution"] = "deja_confirme"
        return ecriture.compte_ht, raisons

    # 2. Plan comptable exact de l'entreprise.
    resolution_plan = plan_comptable_service.resoudre_compte_par_famille(
        db,
        cabinet_id=document.cabinet_id,
        entreprise_id=document.entreprise_id,
        famille_cgnc=regle.famille_cgnc,
        type_usage="ht",
        nature_comptable=nature,
    )

    if resolution_plan.compte:
        donnees["compte_ht_resolution"] = "plan_comptable_entreprise"
        donnees["compte_ht_plan_statut"] = resolution_plan.statut

        if regle.traitement == "immobilisation_candidate":
            raisons.append(
                "Immobilisation potentielle : confirmer la politique "
                "du cabinet avant validation définitive."
            )

        return resolution_plan.compte, raisons

    if resolution_plan.statut == "ambigu":
        donnees["compte_ht_resolution"] = "plan_comptable_ambigu"
        donnees["compte_ht_candidats"] = list(resolution_plan.candidats)
        raisons.append(
            "Plusieurs comptes du plan de l'entreprise correspondent à la "
            f"famille {regle.famille_cgnc} : choix automatique refusé."
        )
        return None, raisons

    # 3. Un compte exact explicitement fourni est accepté seulement s'il
    # appartient à la famille attendue.
    compte_fourni = donnees.get("compte_ht")
    if compte_fourni and compte_correspond_a_famille(
        compte_fourni,
        regle.famille_cgnc,
    ):
        compte = str(compte_fourni).strip()
        donnees["compte_ht_resolution"] = "donnee_confirmee"
        return compte, raisons

    # 4. Compatibilité avec l'historique existant pendant la transition.
    compte_historique = _chercher_compte_ht_connu(
        db,
        document,
        nature,
        regle.famille_cgnc,
    )
    if compte_historique:
        donnees["compte_ht_resolution"] = "historique_entreprise"
        if regle.traitement == "immobilisation_candidate":
            raisons.append(
                "Immobilisation potentielle : vérifier la politique "
                "du cabinet avant validation définitive."
            )
        return compte_historique, raisons

    # 5. Jamais de fabrication du numéro exact.
    donnees["compte_ht_resolution"] = "compte_exact_a_configurer"
    raisons.append(
        "Famille CGNC "
        f"{regle.famille_cgnc} ({regle.libelle}) identifiée, "
        "mais aucun compte exact n'est configuré dans le plan de "
        "cette entreprise."
    )

    if regle.traitement == "immobilisation_candidate":
        raisons.append(
            "Achat durable potentiellement immobilisable : validation "
            "humaine requise tant que la politique du cabinet n'est pas "
            "configurée."
        )

    return None, raisons


# ============================================================
# COMPTE PRODUIT / HT VENTE
# ============================================================

def _chercher_compte_ht_vente_connu(
    db: Session,
    document: Document,
    nature_comptable: str,
    famille_cgnc: str,
) -> str | None:
    """Réutilise un compte produit déjà confirmé pour la même nature."""
    if document.entreprise_id is None:
        return None

    candidates = (
        db.query(EcritureComptable)
        .filter(
            EcritureComptable.cabinet_id == document.cabinet_id,
            EcritureComptable.entreprise_id == document.entreprise_id,
            EcritureComptable.type_ecriture == TypeEcritureEnum.VENTE,
            EcritureComptable.compte_ht.isnot(None),
            EcritureComptable.document_id != document.id,
        )
        .order_by(EcritureComptable.created_at.desc())
        .all()
    )

    for candidate in candidates:
        compte = (candidate.compte_ht or "").strip()

        if not compte_correspond_a_famille(compte, famille_cgnc):
            continue

        candidate_document = getattr(candidate, "document", None)
        candidate_donnees = (
            dict(candidate_document.donnees_extraites or {})
            if candidate_document is not None
            else {}
        )

        candidate_nature = normaliser_nature_vente(
            candidate_donnees.get("nature_comptable")
        )

        if candidate_nature == nature_comptable:
            return compte

    return None


def _resoudre_compte_ht_vente(
    db: Session,
    document: Document,
    ecriture: EcritureComptable,
    donnees: dict,
) -> tuple[str | None, list[str]]:
    """
    Résout le compte de produit d'une VENTE.

    Le champ SQL reste ``compte_ht`` car il représente le compte qui reçoit
    le montant HT de la facture, qu'il s'agisse d'un achat ou d'une vente.
    """
    raisons: list[str] = []

    nature = normaliser_nature_vente(
        donnees.get("nature_comptable")
    )

    if nature is None:
        donnees["famille_compte_ht_suggeree"] = None
        donnees["libelle_compte_ht_suggere"] = None
        donnees["traitement_comptable_suggere"] = "produit"
        donnees["compte_ht_resolution"] = "nature_vente_manquante"
        raisons.append(
            "Nature comptable de la vente non déterminée : "
            "compte produit non affecté."
        )
        return ecriture.compte_ht, raisons

    regle = obtenir_regle_vente(nature)
    if regle is None:
        donnees["compte_ht_resolution"] = "nature_vente_non_supportee"
        raisons.append(f"Nature de vente non supportée : {nature}.")
        return ecriture.compte_ht, raisons

    # On conserve la nature canonique VENTE pour l'audit et l'apprentissage.
    donnees["nature_comptable"] = regle.nature
    donnees["famille_compte_ht_suggeree"] = regle.famille_cgnc
    donnees["libelle_compte_ht_suggere"] = regle.libelle
    donnees["traitement_comptable_suggere"] = "produit"

    # 1. Correction humaine existante.
    if ecriture.compte_ht:
        donnees["compte_ht_resolution"] = "deja_confirme"
        if not compte_correspond_a_famille(
            ecriture.compte_ht,
            regle.famille_cgnc,
        ):
            raisons.append(
                "Compte produit déjà confirmé mais différent de la famille "
                f"suggérée {regle.famille_cgnc} : contrôle requis."
            )
        return ecriture.compte_ht, raisons

    # 2. Plan comptable exact de l'entreprise.
    resolution_plan = plan_comptable_service.resoudre_compte_par_famille(
        db,
        cabinet_id=document.cabinet_id,
        entreprise_id=document.entreprise_id,
        famille_cgnc=regle.famille_cgnc,
        type_usage="ht",
        nature_comptable=regle.nature,
    )

    if resolution_plan.compte:
        donnees["compte_ht_resolution"] = "plan_comptable_entreprise"
        donnees["compte_ht_plan_statut"] = resolution_plan.statut
        return resolution_plan.compte, raisons

    if resolution_plan.statut == "ambigu":
        donnees["compte_ht_resolution"] = "plan_comptable_ambigu"
        donnees["compte_ht_candidats"] = list(resolution_plan.candidats)
        raisons.append(
            "Plusieurs comptes produits du plan de l'entreprise correspondent "
            f"à la famille {regle.famille_cgnc} : choix automatique refusé."
        )
        return None, raisons

    # 3. Compte explicitement fourni, accepté uniquement s'il appartient
    # à la famille déterminée par les règles.
    compte_fourni = donnees.get("compte_ht")
    if compte_fourni and compte_correspond_a_famille(
        compte_fourni,
        regle.famille_cgnc,
    ):
        donnees["compte_ht_resolution"] = "donnee_confirmee"
        return str(compte_fourni).strip(), raisons

    # 4. Historique confirmé de la même entreprise.
    compte_historique = _chercher_compte_ht_vente_connu(
        db,
        document,
        regle.nature,
        regle.famille_cgnc,
    )
    if compte_historique:
        donnees["compte_ht_resolution"] = "historique_entreprise"
        return compte_historique, raisons

    # 5. Aucun compte exact : ne jamais fabriquer le numéro.
    donnees["compte_ht_resolution"] = "compte_exact_a_configurer"
    raisons.append(
        "Famille produit CGNC "
        f"{regle.famille_cgnc} ({regle.libelle}) identifiée, "
        "mais aucun compte exact n'est configuré dans le plan de "
        "cette entreprise."
    )

    return None, raisons


# ============================================================
# COMPTE TVA VENTE
# ============================================================

def _chercher_compte_tva_vente_connu(
    db: Session,
    document: Document,
    famille_tva: str,
) -> str | None:
    """Réutilise un compte de TVA facturée déjà confirmé."""
    if document.entreprise_id is None:
        return None

    candidates = (
        db.query(EcritureComptable)
        .filter(
            EcritureComptable.cabinet_id == document.cabinet_id,
            EcritureComptable.entreprise_id == document.entreprise_id,
            EcritureComptable.type_ecriture == TypeEcritureEnum.VENTE,
            EcritureComptable.compte_tva.isnot(None),
            EcritureComptable.document_id != document.id,
        )
        .order_by(EcritureComptable.created_at.desc())
        .all()
    )

    for candidate in candidates:
        compte = (candidate.compte_tva or "").strip()
        if compte_correspond_a_famille(compte, famille_tva):
            return compte

    return None


def _resoudre_compte_tva_vente(
    db: Session,
    document: Document,
    ecriture: EcritureComptable,
    donnees: dict,
    montant_tva: Decimal | None,
) -> tuple[str | None, list[str]]:
    """Résout le compte TVA facturée d'une VENTE sans inventer le compte."""
    raisons: list[str] = []

    if montant_tva is None:
        donnees["famille_compte_tva_suggeree"] = None
        donnees["compte_tva_resolution"] = "montant_tva_absent"
        return ecriture.compte_tva, raisons

    if montant_tva == Decimal("0.00"):
        donnees["famille_compte_tva_suggeree"] = None
        donnees["familles_compte_tva_possibles"] = []
        donnees["compte_tva_resolution"] = "non_applicable_tva_nulle"
        return None, raisons

    famille_tva = obtenir_famille_tva_vente()
    donnees["famille_compte_tva_suggeree"] = famille_tva
    donnees["familles_compte_tva_possibles"] = [famille_tva]

    # 1. Correction humaine existante.
    if ecriture.compte_tva:
        donnees["compte_tva_resolution"] = "deja_confirme"
        if not compte_correspond_a_famille(ecriture.compte_tva, famille_tva):
            raisons.append(
                "Compte TVA de vente déjà confirmé mais différent de la "
                f"famille {famille_tva} : contrôle requis."
            )
        return ecriture.compte_tva, raisons

    # 2. Plan comptable exact de l'entreprise.
    resolution_plan = plan_comptable_service.resoudre_compte_par_famille(
        db,
        cabinet_id=document.cabinet_id,
        entreprise_id=document.entreprise_id,
        famille_cgnc=famille_tva,
        type_usage="tva",
    )

    if resolution_plan.compte:
        donnees["compte_tva_resolution"] = "plan_comptable_entreprise"
        donnees["compte_tva_plan_statut"] = resolution_plan.statut
        return resolution_plan.compte, raisons

    if resolution_plan.statut == "ambigu":
        donnees["compte_tva_resolution"] = "plan_comptable_ambigu"
        donnees["compte_tva_candidats"] = list(resolution_plan.candidats)
        raisons.append(
            "Plusieurs comptes TVA du plan de l'entreprise correspondent "
            f"à la famille {famille_tva} : choix automatique refusé."
        )
        return None, raisons

    # 3. Donnée explicitement fournie.
    compte_fourni = donnees.get("compte_tva")
    if compte_fourni and compte_correspond_a_famille(
        compte_fourni,
        famille_tva,
    ):
        donnees["compte_tva_resolution"] = "donnee_confirmee"
        return str(compte_fourni).strip(), raisons

    # 4. Historique confirmé de la même entreprise.
    compte_historique = _chercher_compte_tva_vente_connu(
        db,
        document,
        famille_tva,
    )
    if compte_historique:
        donnees["compte_tva_resolution"] = "historique_entreprise"
        return compte_historique, raisons

    # 5. Pas de faux compte complet.
    donnees["compte_tva_resolution"] = "compte_exact_a_configurer"
    raisons.append(
        f"Famille TVA {FAMILLE_TVA_FACTUREE} (Etat - TVA facturée) "
        "identifiée, mais aucun compte exact n'est configuré dans le "
        "plan de cette entreprise."
    )

    return None, raisons


# ============================================================
# COMPTE TVA ACHAT
# ============================================================

def _chercher_compte_tva_connu(
    db: Session,
    document: Document,
    famille_tva: str,
) -> str | None:
    """
    Réutilise un compte TVA exact déjà confirmé dans la même entreprise.

    Contrairement au compte HT, la TVA sur charges / immobilisations est
    généralement commune à plusieurs natures d'achats. On exige simplement
    que le compte historique appartienne à la famille attendue.
    """
    if document.entreprise_id is None:
        return None

    candidates = (
        db.query(EcritureComptable)
        .filter(
            EcritureComptable.cabinet_id == document.cabinet_id,
            EcritureComptable.entreprise_id == document.entreprise_id,
            EcritureComptable.type_ecriture == TypeEcritureEnum.ACHAT,
            EcritureComptable.compte_tva.isnot(None),
            EcritureComptable.document_id != document.id,
        )
        .order_by(EcritureComptable.created_at.desc())
        .all()
    )

    for candidate in candidates:
        compte = (candidate.compte_tva or "").strip()

        if compte_correspond_a_famille(
            compte,
            famille_tva,
        ):
            return compte

    return None


def _resoudre_compte_tva_achat(
    db: Session,
    document: Document,
    ecriture: EcritureComptable,
    donnees: dict,
    montant_tva: Decimal | None,
) -> tuple[str | None, list[str]]:
    """Résout le compte TVA ACHAT avec priorité au plan de l'entreprise."""
    raisons: list[str] = []

    if montant_tva is None:
        donnees["famille_compte_tva_suggeree"] = None
        donnees["compte_tva_resolution"] = "montant_tva_absent"
        return ecriture.compte_tva, raisons

    if montant_tva == Decimal("0.00"):
        donnees["famille_compte_tva_suggeree"] = None
        donnees["familles_compte_tva_possibles"] = []
        donnees["compte_tva_resolution"] = "non_applicable_tva_nulle"
        return None, raisons

    traitement_suggere = donnees.get("traitement_comptable_suggere")
    traitement_confirme = normaliser_traitement_comptable_confirme(
        donnees.get("traitement_comptable_confirme")
    )

    famille_tva = obtenir_famille_tva_achat(
        traitement_suggere,
        traitement_confirme,
    )

    if traitement_confirme is not None:
        donnees["traitement_comptable_effectif"] = traitement_confirme
    elif traitement_suggere == "charge":
        donnees["traitement_comptable_effectif"] = "charge"
    else:
        donnees["traitement_comptable_effectif"] = None

    if famille_tva is None:
        donnees["famille_compte_tva_suggeree"] = None
        donnees["familles_compte_tva_possibles"] = [
            FAMILLE_TVA_RECUPERABLE_IMMOBILISATIONS,
            FAMILLE_TVA_RECUPERABLE_CHARGES,
        ]
        donnees["compte_tva_resolution"] = "traitement_comptable_a_confirmer"
        raisons.append(
            "TVA : l'achat est une immobilisation potentielle. "
            "Confirmer d'abord charge ou immobilisation avant "
            "d'affecter le compte TVA."
        )
        return ecriture.compte_tva, raisons

    donnees["famille_compte_tva_suggeree"] = famille_tva
    donnees["familles_compte_tva_possibles"] = [famille_tva]

    # 1. Correction humaine existante.
    if ecriture.compte_tva:
        donnees["compte_tva_resolution"] = "deja_confirme"
        if not compte_correspond_a_famille(ecriture.compte_tva, famille_tva):
            raisons.append(
                "Compte TVA déjà confirmé mais différent de la famille "
                f"suggérée {famille_tva} : contrôle requis."
            )
        return ecriture.compte_tva, raisons

    # 2. Plan comptable exact de l'entreprise.
    resolution_plan = plan_comptable_service.resoudre_compte_par_famille(
        db,
        cabinet_id=document.cabinet_id,
        entreprise_id=document.entreprise_id,
        famille_cgnc=famille_tva,
        type_usage="tva",
    )

    if resolution_plan.compte:
        donnees["compte_tva_resolution"] = "plan_comptable_entreprise"
        donnees["compte_tva_plan_statut"] = resolution_plan.statut
        return resolution_plan.compte, raisons

    if resolution_plan.statut == "ambigu":
        donnees["compte_tva_resolution"] = "plan_comptable_ambigu"
        donnees["compte_tva_candidats"] = list(resolution_plan.candidats)
        raisons.append(
            "Plusieurs comptes TVA du plan de l'entreprise correspondent "
            f"à la famille {famille_tva} : choix automatique refusé."
        )
        return None, raisons

    # 3. Donnée explicitement confirmée.
    compte_fourni = donnees.get("compte_tva")
    if compte_fourni and compte_correspond_a_famille(
        compte_fourni,
        famille_tva,
    ):
        donnees["compte_tva_resolution"] = "donnee_confirmee"
        return str(compte_fourni).strip(), raisons

    # 4. Historique existant pendant la transition.
    compte_historique = _chercher_compte_tva_connu(
        db,
        document,
        famille_tva,
    )
    if compte_historique:
        donnees["compte_tva_resolution"] = "historique_entreprise"
        return compte_historique, raisons

    # 5. Aucun compte exact : ne rien inventer.
    donnees["compte_tva_resolution"] = "compte_exact_a_configurer"
    libelle_famille = (
        "TVA récupérable sur charges"
        if famille_tva == FAMILLE_TVA_RECUPERABLE_CHARGES
        else "TVA récupérable sur immobilisations"
    )
    raisons.append(
        f"Famille TVA {famille_tva} ({libelle_famille}) identifiée, "
        "mais aucun compte exact n'est configuré dans le plan de "
        "cette entreprise."
    )
    return None, raisons


# ============================================================
# CRÉATION ÉCRITURE
# ============================================================

def creer_ecriture_depuis_document(
    db: Session,
    document: Document,
) -> EcritureComptable:
    """
    Transforme automatiquement une facture classée
    en écriture du journal.
    """

    if (
        document.entreprise_id
        is None
    ):

        raise ValueError(
            (
                "Le document doit être rattaché "
                "à une entreprise avant "
                "la création de l'écriture."
            )
        )

    donnees = dict(
        document.donnees_extraites
        or {}
    )

    # --------------------------------------------------------
    # CATÉGORIE
    # --------------------------------------------------------

    categorie_source = (
        donnees.get(
            "categorie"
        )
        or donnees.get(
            "categorie_document"
        )
        or document.categorie
    )

    type_ecriture = (
        _determiner_type_ecriture(
            categorie_source
        )
    )

    # --------------------------------------------------------
    # DEVISE -> MONTANTS COMPTABLES MAD
    # --------------------------------------------------------
    # Les montants originaux restent dans `donnees`. Le service renvoie
    # une copie temporaire avec HT/TVA/TTC convertis en MAD uniquement
    # pour l'écriture comptable. En cas de taux introuvable, aucun montant
    # en devise n'est pris par erreur pour un montant en MAD.
    conversion_devise = (
        exchange_rate_service
        .preparer_facture_pour_comptabilite(
            db,
            donnees,
            type_ecriture=(
                type_ecriture.value
                if hasattr(type_ecriture, "value")
                else str(type_ecriture)
            ),
        )
    )

    donnees_comptables = (
        conversion_devise
        .donnees_comptables
    )

    # --------------------------------------------------------
    # TAUX TVA
    # --------------------------------------------------------

    taux_enum = (
        _normaliser_taux_tva(
            donnees.get(
                "taux_tva"
            )
        )
    )

    # --------------------------------------------------------
    # MONTANTS
    # --------------------------------------------------------

    (
        ht,
        tva,
        ttc,
        anomalie_montants,
        message_montants,
    ) = (
        _lire_montants_et_controler(
            donnees_comptables
        )
    )

    # --------------------------------------------------------
    # ANOMALIES EXTRACTION
    # --------------------------------------------------------

    anomalie_extraction = bool(
        donnees.get(
            "a_verifier"
        )
    )

    raison_extraction = (
        donnees.get(
            "raison_verification"
        )
    )

    raisons = [
        str(
            raison
        ).strip()

        for raison in (
            message_montants,
            raison_extraction,
            *conversion_devise.raisons,
        )

        if (
            raison is not None
            and str(
                raison
            ).strip()
        )
    ]

    anomalie_detectee = (
        anomalie_montants
        or anomalie_extraction
    )

    anomalie_details = (
        " | ".join(
            raisons
        )
        or None
    )

    # --------------------------------------------------------
    # DATE
    # --------------------------------------------------------

    date_piece: date_type | None = None

    date_piece_str = (
        donnees.get(
            "date_piece"
        )
    )

    if date_piece_str:

        try:
            date_piece = (
                date_type.fromisoformat(
                    str(
                        date_piece_str
                    )
                )
            )

        except ValueError:
            date_piece = None

    workflow_comptable_service.verifier_date_modifiable(
        db,
        cabinet_id=document.cabinet_id,
        entreprise_id=document.entreprise_id,
        target_date=date_piece or workflow_comptable_service.date_document(document),
    )

    # --------------------------------------------------------
    # ÉCRITURE EXISTANTE
    # --------------------------------------------------------

    existing_entries = (
        db.query(
            EcritureComptable
        )
        .filter(
            EcritureComptable.document_id
            == document.id
        )
        .order_by(
            EcritureComptable
            .created_at
            .asc()
        )
        .all()
    )

    if existing_entries:

        ecriture = (
            existing_entries[
                0
            ]
        )

        # Protection contre anciens doublons.
        for duplicate in (
            existing_entries[
                1:
            ]
        ):
            db.delete(
                duplicate
            )

    else:

        ecriture = (
            EcritureComptable(
                cabinet_id=
                    document.cabinet_id,

                document_id=
                    document.id,

                entreprise_id=
                    document.entreprise_id,

                type_ecriture=
                    type_ecriture,

                montant_ttc=
                    ttc,
            )
        )

        db.add(
            ecriture
        )

    # --------------------------------------------------------
    # TIERS
    # --------------------------------------------------------

    tiers = (
        donnees.get(
            "tiers"
        )
    )

    numero_piece = (
        donnees.get(
            "numero_piece"
        )
    )

    # --------------------------------------------------------
    # COMPTE FOURNISSEUR / CLIENT
    # --------------------------------------------------------

    # Priorité :
    #
    # 1. compte déjà confirmé sur l'écriture
    # 2. compte éventuellement fourni
    # 3. ancien compte du même tiers
    # 4. DIVERS

    compte_tiers_existant = (
        ecriture.compte_tiers
        if _compte_tiers_est_compatible(
            ecriture.compte_tiers,
            type_ecriture,
        )
        else None
    )

    compte_tiers_fourni = donnees.get("compte_tiers")

    if not _compte_tiers_est_compatible(
        compte_tiers_fourni,
        type_ecriture,
    ):
        compte_tiers_fourni = None

    usage_tiers = (
        "fournisseur"
        if type_ecriture == TypeEcritureEnum.ACHAT
        else "client"
        if type_ecriture == TypeEcritureEnum.VENTE
        else None
    )

    compte_tiers_plan: str | None = None
    compte_divers_plan: str | None = None
    tiers_plan_ambigu = False

    if usage_tiers is not None:
        resolution_tiers_plan = plan_comptable_service.chercher_compte_tiers(
            db,
            cabinet_id=document.cabinet_id,
            entreprise_id=document.entreprise_id,
            tiers=str(tiers) if tiers else None,
            type_usage=usage_tiers,
        )

        if resolution_tiers_plan.compte:
            compte_tiers_plan = resolution_tiers_plan.compte
            donnees["compte_tiers_resolution"] = "plan_comptable_entreprise"
        elif resolution_tiers_plan.statut == "ambigu":
            tiers_plan_ambigu = True
            donnees["compte_tiers_resolution"] = "plan_comptable_ambigu"
            donnees["compte_tiers_candidats"] = list(
                resolution_tiers_plan.candidats
            )
            raisons.append(
                "Plusieurs comptes tiers du plan correspondent au même tiers : "
                "choix automatique refusé."
            )
            anomalie_detectee = True

        resolution_divers = plan_comptable_service.chercher_compte_divers(
            db,
            cabinet_id=document.cabinet_id,
            entreprise_id=document.entreprise_id,
            type_usage=usage_tiers,
        )
        if resolution_divers.compte:
            compte_divers_plan = resolution_divers.compte

    compte_tiers_historique = _chercher_compte_tiers_connu(
        db,
        document,
        type_ecriture,
        str(tiers) if tiers else None,
    )

    compte_tiers, compte_tiers_source = _choisir_compte_tiers(
        type_ecriture=type_ecriture,
        compte_existant=compte_tiers_existant,
        compte_plan=compte_tiers_plan,
        compte_fourni=compte_tiers_fourni,
        compte_historique=compte_tiers_historique,
        compte_divers_plan=compte_divers_plan,
    )
    donnees["compte_tiers_source"] = compte_tiers_source

    if not tiers_plan_ambigu:
        donnees["compte_tiers_resolution"] = compte_tiers_source

    # --------------------------------------------------------
    # MOTEUR COMPTE HT : ACHAT OU VENTE
    # --------------------------------------------------------

    compte_ht_resolu: str | None = (
        ecriture.compte_ht
        or donnees.get("compte_ht")
    )

    raisons_comptables: list[str] = []

    if type_ecriture == TypeEcritureEnum.ACHAT:
        (
            compte_ht_resolu,
            raisons_comptables,
        ) = _resoudre_compte_ht_achat(
            db,
            document,
            ecriture,
            donnees,
        )

    elif type_ecriture == TypeEcritureEnum.VENTE:
        (
            compte_ht_resolu,
            raisons_comptables,
        ) = _resoudre_compte_ht_vente(
            db,
            document,
            ecriture,
            donnees,
        )

    for raison in raisons_comptables:
        if raison not in raisons:
            raisons.append(raison)

    if raisons_comptables:
        anomalie_detectee = True

    anomalie_details = (
        " | ".join(raisons)
        or None
    )

    # --------------------------------------------------------
    # MOTEUR TVA : ACHAT OU VENTE
    # --------------------------------------------------------

    compte_tva_resolu: str | None = (
        ecriture.compte_tva
        or donnees.get("compte_tva")
    )

    raisons_tva: list[str] = []

    if type_ecriture == TypeEcritureEnum.ACHAT:
        (
            compte_tva_resolu,
            raisons_tva,
        ) = _resoudre_compte_tva_achat(
            db,
            document,
            ecriture,
            donnees,
            tva,
        )

    elif type_ecriture == TypeEcritureEnum.VENTE:
        (
            compte_tva_resolu,
            raisons_tva,
        ) = _resoudre_compte_tva_vente(
            db,
            document,
            ecriture,
            donnees,
            tva,
        )

    for raison in raisons_tva:
        if raison not in raisons:
            raisons.append(raison)

    if raisons_tva:
        anomalie_detectee = True

    anomalie_details = (
        " | ".join(raisons)
        or None
    )

    # --------------------------------------------------------
    # REMPLISSAGE ÉCRITURE
    # --------------------------------------------------------

    ecriture.cabinet_id = (
        document.cabinet_id
    )

    ecriture.document_id = (
        document.id
    )

    ecriture.entreprise_id = (
        document.entreprise_id
    )

    ecriture.type_ecriture = (
        type_ecriture
    )

    ecriture.numero_piece = (
        numero_piece
    )

    ecriture.date_piece = (
        date_piece
    )

    ecriture.tiers = (
        tiers
    )

    # --------------------------------------------------------
    # COMPTES
    # --------------------------------------------------------

    ecriture.compte_tiers = (
        compte_tiers
    )

    ecriture.compte_tva = (
        compte_tva_resolu
    )

    ecriture.compte_ht = (
        compte_ht_resolu
    )

    # --------------------------------------------------------
    # LIBELLÉ AUTOMATIQUE
    # --------------------------------------------------------

    ecriture.libelle = (
        _construire_libelle(
            tiers,
            numero_piece,
        )
    )

    # --------------------------------------------------------
    # MONTANTS EXTRAITS
    # --------------------------------------------------------

    ecriture.montant_ht = (
        ht
    )

    ecriture.taux_tva = (
        taux_enum
    )

    ecriture.montant_tva = (
        tva
    )

    ecriture.montant_ttc = (
        ttc
    )

    # --------------------------------------------------------
    # DEVISES V2 — VALEUR INITIALE AUDITABLE
    # --------------------------------------------------------
    devise_initiale = str(
        donnees.get("devise_originale") or donnees.get("devise") or "MAD"
    ).upper()
    ecriture.devise_originale = devise_initiale
    ecriture.montant_ttc_devise = (
        _vers_decimal(donnees.get("montant_ttc_devise"))
        if devise_initiale != "MAD"
        else ttc
    )
    ecriture.montant_ttc_mad = (
        _vers_decimal(donnees.get("montant_ttc_mad")) or ttc
    )
    ecriture.taux_change_initial = _vers_decimal(donnees.get("taux_change"))
    try:
        ecriture.unite_cotation_initiale = int(donnees.get("unite_cotation"))
    except (TypeError, ValueError):
        ecriture.unite_cotation_initiale = 1 if devise_initiale == "MAD" else None
    try:
        ecriture.date_cours_initial = date_type.fromisoformat(
            str(donnees.get("date_cours_change"))
        )
    except (TypeError, ValueError):
        ecriture.date_cours_initial = None
    ecriture.type_cours_initial = donnees.get("type_cours_change")
    ecriture.source_cours_initial = donnees.get("source_cours_change")

    # --------------------------------------------------------
    # STATUT
    # --------------------------------------------------------

    ecriture.statut_validation = (
        StatutValidationEnum
        .A_VERIFIER

        if anomalie_detectee

        else StatutValidationEnum
        .BROUILLON
    )

    ecriture.validated_by = None

    ecriture.anomalie_detectee = (
        anomalie_detectee
    )

    ecriture.anomalie_details = (
        anomalie_details
    )

    # --------------------------------------------------------
    # LIGNES DÉBIT / CRÉDIT
    # --------------------------------------------------------
    # Les lignes sont créées même au stade brouillon pour permettre
    # leur prévisualisation, mais elles ne deviennent éligibles au
    # Grand Livre qu'après validation de l'écriture.
    db.flush()
    generation_lignes = (
        ligne_comptable_service
        .synchroniser_lignes_facture(
            db,
            ecriture,
        )
    )

    if generation_lignes.applicable and not generation_lignes.complet:
        for raison in generation_lignes.raisons:
            if raison not in raisons:
                raisons.append(raison)

        ecriture.statut_validation = (
            StatutValidationEnum.A_VERIFIER
        )
        ecriture.validated_by = None
        ecriture.anomalie_detectee = True
        ecriture.anomalie_details = (
            " | ".join(raisons)
            or None
        )

    donnees["lignes_comptables_statut"] = (
        "complete"
        if generation_lignes.complet
        else "a_verifier"
        if generation_lignes.applicable
        else "non_applicable"
    )
    donnees["nombre_lignes_comptables"] = len(
        generation_lignes.lignes
    )

    # Les documents sans anomalie passent automatiquement à PRETE_TOPAZE.
    # Une correction ultérieure relancera exactement le même contrôle.
    workflow_comptable_service.controler_et_transitionner(
        db,
        ecriture,
        document=document,
        actor_type="celery",
    )
    donnees["workflow_comptable_statut"] = ecriture.statut_validation.value

    # Les métadonnées du moteur comptable restent visibles
    # dans le document pour audit / interface / futur apprentissage.
    document.donnees_extraites = dict(donnees)

    db.commit()

    db.refresh(
        ecriture
    )

    return ecriture


# ============================================================
# MOUVEMENTS BANCAIRES
# ============================================================

def creer_mouvements_bancaires(
    db: Session,
    document: Document,
) -> list[MouvementBancaire]:
    """
    Crée une ligne SQL pour chaque ligne extraite
    du relevé bancaire.

    Cette partie reste indépendante du Journal
    d'Achat.
    """

    from app.models.enums import (
        TypeMouvementBancaireEnum,
    )

    if (
        document.entreprise_id
        is None
    ):

        raise ValueError(
            (
                "Le relevé bancaire doit être "
                "rattaché à une entreprise avant "
                "la création de ses mouvements."
            )
        )

    donnees = dict(
        document.donnees_extraites
        or {}
    )

    raw_lines = (
        donnees.get(
            "lignes_bancaires"
        )
    )

    lignes_extraites = (
        raw_lines
        if isinstance(
            raw_lines,
            list,
        )
        else []
    )

    # Préflight complet avant la suppression/recréation des mouvements : une
    # seule ligne appartenant à une période verrouillée bloque tout le lot.
    workflow_comptable_service.verifier_document_modifiable(db, document)
    for raw_line in lignes_extraites:
        value = raw_line.get("date_operation") if isinstance(raw_line, dict) else None
        try:
            operation_date = date_type.fromisoformat(str(value))
        except (TypeError, ValueError):
            operation_date = document.created_at.date()
        workflow_comptable_service.verifier_date_modifiable(
            db,
            cabinet_id=document.cabinet_id,
            entreprise_id=document.entreprise_id,
            target_date=operation_date,
        )

    # --------------------------------------------------------
    # ANTI-DOUBLON
    # --------------------------------------------------------

    (
        db.query(
            MouvementBancaire
        )
        .filter(
            MouvementBancaire.document_id
            == document.id
        )
        .delete(
            synchronize_session=False
        )
    )

    mouvements_crees: list[
        MouvementBancaire
    ] = []

    lignes_normalisees: list[
        dict
    ] = []

    # --------------------------------------------------------
    # LIGNES
    # --------------------------------------------------------

    for (
        index,
        raw_line,
    ) in enumerate(
        lignes_extraites,
        start=1,
    ):

        ligne = (
            dict(
                raw_line
            )

            if isinstance(
                raw_line,
                dict,
            )

            else {
                "texte_brut":
                    str(
                        raw_line
                    )
            }
        )

        raisons: list[
            str
        ] = []

        def add_reason(
            message: str,
        ) -> None:

            if (
                message
                and message
                not in raisons
            ):
                raisons.append(
                    message
                )

        # ----------------------------------------------------
        # DATE
        # ----------------------------------------------------

        date_obj: date_type

        date_value = (
            ligne.get(
                "date_operation"
            )
        )

        try:

            date_obj = (
                date_type.fromisoformat(
                    str(
                        date_value
                    )
                )
            )

        except (
            TypeError,
            ValueError,
        ):

            date_obj = (
                document
                .created_at
                .date()
            )

            add_reason(
                (
                    "Date d'opération non détectée : "
                    "date d'import utilisée "
                    "provisoirement."
                )
            )

        # ----------------------------------------------------
        # MONTANTS
        # ----------------------------------------------------

        debit = (
            _vers_decimal(
                ligne.get(
                    "debit"
                )
            )
        )

        credit = (
            _vers_decimal(
                ligne.get(
                    "credit"
                )
            )
        )

        montant = (
            _vers_decimal(
                ligne.get(
                    "montant"
                )
            )
        )

        raw_type = str(
            ligne.get(
                "type_mouvement"
            )
            or ""
        ).strip().lower()

        if raw_type in {
            "credit",
            "crédit",
            "depot",
            "dépôt",
            "encaissement",
        }:

            mouvement_type = (
                TypeMouvementBancaireEnum
                .CREDIT
            )

        elif raw_type in {
            "debit",
            "débit",
            "retrait",
            "decaissement",
            "décaissement",
        }:

            mouvement_type = (
                TypeMouvementBancaireEnum
                .DEBIT
            )

        elif (
            credit is not None
            and debit is None
        ):

            mouvement_type = (
                TypeMouvementBancaireEnum
                .CREDIT
            )

        elif (
            debit is not None
            and credit is None
        ):

            mouvement_type = (
                TypeMouvementBancaireEnum
                .DEBIT
            )

        else:

            mouvement_type = (
                TypeMouvementBancaireEnum
                .DEBIT
            )

            add_reason(
                (
                    "Type débit/crédit non déterminé : "
                    "débit provisoire."
                )
            )

        if montant is None:

            if (
                mouvement_type
                == TypeMouvementBancaireEnum
                .CREDIT
            ):

                montant = (
                    credit
                )

            else:

                montant = (
                    debit
                )

        if montant is None:

            montant = (
                Decimal(
                    "0.00"
                )
            )

            add_reason(
                (
                    "Montant non détecté : "
                    "0,00 MAD provisoire."
                )
            )

        # ----------------------------------------------------
        # DEVISE BANCAIRE
        # ----------------------------------------------------
        devise_ligne = (
            ligne.get("devise")
            or donnees.get("devise")
            or "MAD"
        )

        conversion_banque = (
            exchange_rate_service
            .convertir_mouvement_bancaire(
                db,
                date_operation=date_obj,
                devise=devise_ligne,
                type_mouvement=(
                    mouvement_type.value
                    if hasattr(mouvement_type, "value")
                    else str(mouvement_type)
                ),
                montant=montant,
                montant_mad_reel=(
                    _vers_decimal(ligne.get("montant_mad_reel"))
                    or _vers_decimal(ligne.get("montant_reglement_mad"))
                    or _vers_decimal(ligne.get("montant_debite_mad"))
                    or _vers_decimal(ligne.get("montant_credite_mad"))
                ),
            )
        )

        montant_comptable = (
            conversion_banque.montant_mad
        )

        if conversion_banque.raison:
            add_reason(conversion_banque.raison)

        if montant_comptable is None:
            # Sécurité : ne jamais enregistrer 1 000 EUR comme 1 000 MAD.
            montant_comptable = Decimal("0.00")
            add_reason(
                conversion_banque.raison
                or "Conversion devise bancaire impossible : 0,00 MAD provisoire."
            )

        solde = (
            _vers_decimal(
                ligne.get(
                    "solde_apres_operation"
                )
            )
        )

        # ----------------------------------------------------
        # LIBELLÉ
        # ----------------------------------------------------

        libelle = str(
            ligne.get(
                "libelle_original"
            )
            or ligne.get(
                "libelle"
            )
            or ligne.get(
                "texte_brut"
            )
            or "Ligne bancaire à vérifier"
        ).strip()

        if not libelle:

            libelle = (
                "Ligne bancaire à vérifier"
            )

            add_reason(
                "Libellé non détecté."
            )

        reference = (
            ligne.get(
                "reference"
            )
            or ligne.get(
                "code_operation"
            )
        )

        if reference is not None:

            reference = (
                str(
                    reference
                )
                .strip()[
                    :100
                ]
                or None
            )

        existing_reason = (
            ligne.get(
                "raison_verification"
            )
        )

        if existing_reason:
            add_reason(
                str(
                    existing_reason
                )
            )

        # ----------------------------------------------------
        # JSON NORMALISÉ
        # ----------------------------------------------------

        ligne[
            "ordre"
        ] = int(
            ligne.get(
                "ordre"
            )
            or index
        )

        ligne[
            "date_operation"
        ] = (
            date_obj.isoformat()
        )

        ligne[
            "libelle"
        ] = (
            libelle[
                :500
            ]
        )

        ligne[
            "reference"
        ] = (
            reference
        )

        ligne[
            "type_mouvement"
        ] = (
            mouvement_type.name
        )

        ligne[
            "montant"
        ] = float(
            montant_comptable
        )

        ligne["devise_originale"] = (
            conversion_banque.devise_originale
        )
        ligne["montant_devise"] = format(
            conversion_banque.montant_devise,
            "f",
        )
        ligne["montant_mad"] = (
            format(conversion_banque.montant_mad, "f")
            if conversion_banque.montant_mad is not None
            else None
        )
        ligne["montant_mad_theorique"] = (
            format(conversion_banque.montant_mad_theorique, "f")
            if conversion_banque.montant_mad_theorique is not None
            else None
        )
        ligne["montant_mad_source"] = conversion_banque.montant_mad_source
        ligne["taux_change"] = (
            format(conversion_banque.taux_change, "f")
            if conversion_banque.taux_change is not None
            else None
        )
        ligne["type_cours_change"] = (
            conversion_banque.type_cours_change
        )
        ligne["date_cours_change"] = (
            conversion_banque.date_cours_change.isoformat()
            if conversion_banque.date_cours_change is not None
            else None
        )
        ligne["unite_cotation"] = (
            conversion_banque.unite_cotation
        )
        ligne["source_cours_change"] = (
            conversion_banque.source_cours_change
        )

        ligne[
            "solde_apres_operation"
        ] = (
            float(
                solde
            )
            if solde is not None
            else None
        )

        ligne[
            "a_verifier"
        ] = (
            bool(
                raisons
            )
            or bool(
                ligne.get(
                    "a_verifier"
                )
            )
        )

        ligne[
            "raison_verification"
        ] = (
            " | ".join(
                raisons
            )
            if raisons
            else None
        )

        lignes_normalisees.append(
            ligne
        )

        # ----------------------------------------------------
        # SQL
        # ----------------------------------------------------

        mouvement = (
            MouvementBancaire(
                cabinet_id=
                    document.cabinet_id,

                document_id=
                    document.id,

                entreprise_id=
                    document.entreprise_id,

                date_operation=
                    date_obj,

                libelle=
                    libelle[
                        :500
                    ],

                reference=
                    reference,

                type_mouvement=
                    mouvement_type,

                montant=
                    montant_comptable,

                solde_apres_operation=
                    solde,

                devise_originale=
                    conversion_banque.devise_originale,

                montant_devise=
                    conversion_banque.montant_devise,

                montant_mad=
                    conversion_banque.montant_mad,

                montant_mad_theorique=
                    conversion_banque.montant_mad_theorique,

                montant_mad_source=
                    conversion_banque.montant_mad_source,

                taux_change=
                    conversion_banque.taux_change,

                type_cours_change=
                    conversion_banque.type_cours_change,

                date_cours_change=
                    conversion_banque.date_cours_change,

                unite_cotation=
                    conversion_banque.unite_cotation,

                source_cours_change=
                    conversion_banque.source_cours_change,
            )
        )

        db.add(
            mouvement
        )

        mouvements_crees.append(
            mouvement
        )

    # --------------------------------------------------------
    # RETOUR JSON
    # --------------------------------------------------------

    donnees[
        "lignes_bancaires"
    ] = (
        lignes_normalisees
    )

    donnees[
        "nombre_lignes_extraites"
    ] = len(
        lignes_normalisees
    )

    incomplete_count = sum(
        1
        for line in lignes_normalisees
        if line.get(
            "a_verifier"
        )
    )

    if incomplete_count:

        donnees[
            "a_verifier"
        ] = True

        message = (
            f"{incomplete_count} "
            "ligne(s) bancaire(s) "
            "nécessitent une vérification."
        )

        previous = str(
            donnees.get(
                "raison_verification"
            )
            or ""
        ).strip()

        donnees[
            "raison_verification"
        ] = (
            f"{previous} | {message}"

            if (
                previous
                and message not in previous
            )

            else message
        )

        donnees[
            "extraction_bancaire_statut"
        ] = "a_verifier"

    document.donnees_extraites = (
        donnees
    )

    # Les IDs doivent exister avant le rapprochement. Aucun commit intermédiaire :
    # si une erreur SQL survient, la transaction complète reste atomique.
    db.flush()

    for mouvement in mouvements_crees:
        rapprochement_bancaire_service.rapprocher_mouvement(
            db,
            mouvement,
        )

    db.commit()

    for mouvement in (
        mouvements_crees
    ):
        db.refresh(
            mouvement
        )

    return mouvements_crees
