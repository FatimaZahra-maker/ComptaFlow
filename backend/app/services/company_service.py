"""
app/services/company_service.py

Identification de l'entreprise suivie par le cabinet et détermination de la
vue comptable Achat / Vente.

Règle principale pour une facture classique :
- entreprise suivie = fournisseur/émetteur  -> VENTE pour cette entreprise ;
- entreprise suivie = client/destinataire   -> ACHAT pour cette entreprise.

SEGURIBAT est désormais traité comme le CABINET lui-même, pas comme une
entreprise suivie. Le cabinet est lu dans la table ``cabinets`` ; son nom/ICE
ont priorité sur une éventuelle ancienne ligne ``entreprises`` portant le même
nom.

Conséquence :
- SEGURIBAT -> ANZOBAT, si ANZOBAT est suivie : document rattaché à ANZOBAT,
  catégorie ACHATS, avec SEGURIBAT comme fournisseur ;
- ANZOBAT -> SEGURIBAT, si ANZOBAT est suivie : document rattaché à ANZOBAT,
  catégorie VENTES, avec SEGURIBAT comme client ;
- facture propre au cabinet avec l'autre partie non suivie : le document est
  marqué ``traitement_cabinet_propre`` et n'est pas forcé dans un faux dossier
  entreprise.

Les sociétés créées automatiquement par le pipeline restent visibles en base,
mais ne sont pas considérées comme des dossiers comptables suivis tant qu'un
humain ne les a pas confirmées (``creee_automatiquement=False``).
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.models.cabinet import Cabinet
from app.models.entreprise import Entreprise

_PLACEHOLDER = "Entreprise à identifier"
_FORMES_JURIDIQUES = {
    "SARL",
    "SARLAU",
    "SA",
    "SAS",
    "SASU",
    "SNC",
    "STE",
    "SOCIETE",
    "ETABLISSEMENT",
    "ETABLISSEMENTS",
    "ETS",
}


def _normaliser_identifiant(valeur: Any) -> str | None:
    if valeur in (None, ""):
        return None
    texte = re.sub(r"[^A-Za-z0-9]", "", str(valeur)).upper().strip()
    return texte or None


def _normaliser_nom(valeur: Any) -> str | None:
    if valeur in (None, ""):
        return None

    texte = str(valeur).upper().strip()
    if not texte:
        return None

    texte = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texte)
        if unicodedata.category(caractere) != "Mn"
    )
    texte = re.sub(r"[^A-Z0-9]+", " ", texte)
    mots = [mot for mot in texte.split() if mot not in _FORMES_JURIDIQUES]
    resultat = " ".join(mots).strip()
    return resultat or None


def _cle_comparaison_nom(valeur: Any) -> str | None:
    """Clé stricte après la normalisation existante, sans fuzzy matching.

    La suppression des espaces permet seulement de neutraliser une coupure OCR
    ou un séparateur typographique (``SEGURI-BAT`` / ``SEGURI BAT``). Aucun
    caractère n'est substitué et aucune distance approximative n'est utilisée.
    """
    normalise = _normaliser_nom(valeur)
    return normalise.replace(" ", "") if normalise else None


def _type_document(donnees: dict) -> str | None:
    return (
        donnees.get("type_document")
        or donnees.get("categorie_document")
    )


def _charger_cabinet(
    db: Session,
    cabinet_id: uuid.UUID,
) -> Cabinet | None:
    return (
        db.query(Cabinet)
        .filter(
            Cabinet.id == cabinet_id,
            Cabinet.is_active.is_(True),
        )
        .first()
    )


def _correspond_au_cabinet(
    cabinet: Cabinet | None,
    *,
    ice: Any = None,
    nom: Any = None,
) -> bool:
    """Compare une partie extraite à l'identité officielle du cabinet."""
    if cabinet is None:
        return False

    ice_cabinet = _normaliser_identifiant(cabinet.ice)
    ice_partie = _normaliser_identifiant(ice)
    if ice_cabinet and ice_partie and ice_cabinet == ice_partie:
        return True

    nom_cabinet = _cle_comparaison_nom(cabinet.nom)
    nom_partie = _cle_comparaison_nom(nom)
    if nom_cabinet and nom_partie and nom_cabinet == nom_partie:
        return True

    return False


def _entreprises_suivies(
    db: Session,
    cabinet_id: uuid.UUID,
) -> list[Entreprise]:
    """
    Retourne uniquement les dossiers comptables confirmés.

    Les anciennes sociétés auto-créées ne sont PAS supprimées ni cachées de
    l'interface ; elles sont simplement exclues de la décision Achat/Vente.
    """
    return list(
        db.query(Entreprise)
        .filter(
            Entreprise.cabinet_id == cabinet_id,
            Entreprise.is_active.is_(True),
            Entreprise.creee_automatiquement.is_(False),
        )
        .all()
    )


def _rechercher_entreprise_suivie(
    db: Session,
    cabinet_id: uuid.UUID,
    *,
    ice: Any = None,
    identifiant_fiscal: Any = None,
    rc: Any = None,
    nom: Any = None,
    cabinet: Cabinet | None = None,
) -> Entreprise | None:
    """ICE -> IF -> RC -> nom normalisé, dans les dossiers suivis."""

    # Le cabinet lui-même ne doit jamais être renvoyé comme entreprise suivie,
    # même si une vieille ligne Entreprise "SEGURIBAT" existe encore.
    if _correspond_au_cabinet(cabinet, ice=ice, nom=nom):
        return None

    ice_n = _normaliser_identifiant(ice)
    if_n = _normaliser_identifiant(identifiant_fiscal)
    rc_n = _normaliser_identifiant(rc)
    nom_n = _normaliser_nom(nom)

    entreprises = _entreprises_suivies(db, cabinet_id)

    if ice_n:
        for entreprise in entreprises:
            if _normaliser_identifiant(entreprise.ice) == ice_n:
                return entreprise

    if if_n:
        for entreprise in entreprises:
            if _normaliser_identifiant(entreprise.identifiant_fiscal) == if_n:
                return entreprise

    if rc_n:
        for entreprise in entreprises:
            if _normaliser_identifiant(entreprise.rc) == rc_n:
                return entreprise

    if nom_n:
        for entreprise in entreprises:
            if _normaliser_nom(entreprise.nom) == nom_n:
                return entreprise

    return None


def _obtenir_placeholder(
    db: Session,
    cabinet_id: uuid.UUID,
) -> Entreprise:
    """
    Dossier technique pour les documents impossibles à rattacher avec sûreté.

    On ne transforme plus automatiquement chaque fournisseur externe en
    entreprise suivie du cabinet.
    """
    entreprise = (
        db.query(Entreprise)
        .filter(
            Entreprise.cabinet_id == cabinet_id,
            Entreprise.nom == _PLACEHOLDER,
            Entreprise.is_active.is_(True),
        )
        .first()
    )

    if entreprise is not None:
        return entreprise

    entreprise = Entreprise(
        cabinet_id=cabinet_id,
        nom=_PLACEHOLDER,
        creee_automatiquement=True,
        is_active=True,
    )
    db.add(entreprise)
    db.commit()
    db.refresh(entreprise)
    return entreprise


def identifier_ou_creer_entreprise(
    db: Session,
    cabinet_id: uuid.UUID,
    donnees: dict,
) -> Entreprise:
    """
    Compatibilité pour les documents hors facture.

    On recherche un dossier confirmé ; sinon on utilise le dossier technique
    "Entreprise à identifier" au lieu d'inventer une entreprise suivie.
    """
    cabinet = _charger_cabinet(db, cabinet_id)

    entreprise = _rechercher_entreprise_suivie(
        db,
        cabinet_id,
        ice=donnees.get("ice"),
        identifiant_fiscal=donnees.get("identifiant_fiscal"),
        rc=donnees.get("rc"),
        nom=donnees.get("nom_entreprise"),
        cabinet=cabinet,
    )

    return entreprise or _obtenir_placeholder(db, cabinet_id)


def _marquer_relation_cabinet(
    donnees: dict,
    cabinet: Cabinet,
    role_cabinet: str,
    traitement_cabinet_propre: bool,
) -> None:
    donnees["implique_cabinet"] = True
    donnees["cabinet_nom"] = cabinet.nom
    donnees["role_cabinet"] = role_cabinet
    donnees["traitement_cabinet_propre"] = traitement_cabinet_propre


def identifier_entreprise_et_direction(
    db: Session,
    cabinet_id: uuid.UUID,
    donnees: dict,
) -> tuple[Entreprise | None, str | None, str | None]:
    """
    Retourne ``(entreprise_suivie, direction, tiers_nom)``.

    ``direction`` vaut ``achats`` ou ``ventes`` depuis le point de vue du
    dossier comptable auquel le document est rattaché.

    Si la facture appartient à la comptabilité PROPRE du cabinet et qu'aucun
    autre dossier suivi n'est concerné, ``entreprise_suivie`` vaut ``None``.
    Le pipeline la conserve alors comme document cabinet sans créer un faux
    chrono entreprise ni une fausse écriture.
    """
    type_doc = _type_document(donnees)
    cabinet = _charger_cabinet(db, cabinet_id)

    # Réinitialiser les marqueurs pour un retraitement propre/idempotent.
    donnees["implique_cabinet"] = False
    donnees["traitement_cabinet_propre"] = False
    donnees.pop("role_cabinet", None)
    donnees.pop("cabinet_nom", None)
    donnees.pop("direction_a_verifier", None)

    if type_doc in ("releve_bancaire", "avis_cnss", "avis_tva"):
        entreprise = identifier_ou_creer_entreprise(db, cabinet_id, donnees)
        return entreprise, None, None

    nom_fournisseur = donnees.get("nom_fournisseur")
    nom_client = donnees.get("nom_client")
    ice_fournisseur = donnees.get("ice_fournisseur")
    if_fournisseur = donnees.get("if_fournisseur")
    rc_fournisseur = donnees.get("rc_fournisseur")

    # Le fallback OCR/Ollama historique expose uniquement ces deux rôles :
    # nom_entreprise = émetteur, tiers = destinataire. On ne les emploie que
    # lorsque les DEUX champs structurés sont absents, afin de ne jamais
    # écraser une extraction Vision partielle ni d'inverser une partie connue.
    if (
        type_doc == "facture"
        and not nom_fournisseur
        and not nom_client
    ):
        nom_fournisseur = donnees.get("nom_entreprise")
        nom_client = donnees.get("tiers")
        ice_fournisseur = donnees.get("ice")
        if_fournisseur = donnees.get("identifiant_fiscal")
        rc_fournisseur = donnees.get("rc")

    fournisseur_est_cabinet = _correspond_au_cabinet(
        cabinet,
        ice=ice_fournisseur,
        nom=nom_fournisseur,
    )
    client_est_cabinet = _correspond_au_cabinet(
        cabinet,
        ice=donnees.get("ice_client"),
        nom=nom_client,
    )

    fournisseur = _rechercher_entreprise_suivie(
        db,
        cabinet_id,
        ice=ice_fournisseur,
        identifiant_fiscal=if_fournisseur,
        rc=rc_fournisseur,
        nom=nom_fournisseur,
        cabinet=cabinet,
    )

    client = _rechercher_entreprise_suivie(
        db,
        cabinet_id,
        ice=donnees.get("ice_client"),
        identifiant_fiscal=donnees.get("if_client"),
        rc=donnees.get("rc_client"),
        nom=nom_client,
        cabinet=cabinet,
    )

    # ========================================================
    # FACTURES IMPLIQUANT LE CABINET
    # ========================================================

    if cabinet is not None and fournisseur_est_cabinet and not client_est_cabinet:
        if client is not None:
            # SEGURIBAT -> entreprise suivie : ACHAT dans le dossier client.
            _marquer_relation_cabinet(
                donnees,
                cabinet,
                role_cabinet="fournisseur",
                traitement_cabinet_propre=False,
            )
            return client, "achats", nom_fournisseur or cabinet.nom

        # Sans dossier client suivi, ne pas choisir arbitrairement une vente.
        _marquer_relation_cabinet(
            donnees,
            cabinet,
            role_cabinet="fournisseur",
            traitement_cabinet_propre=True,
        )
        donnees["direction_a_verifier"] = True
        return None, None, nom_client

    if cabinet is not None and client_est_cabinet and not fournisseur_est_cabinet:
        if fournisseur is not None:
            # entreprise suivie -> SEGURIBAT : VENTE dans le dossier fournisseur.
            _marquer_relation_cabinet(
                donnees,
                cabinet,
                role_cabinet="client",
                traitement_cabinet_propre=False,
            )
            return fournisseur, "ventes", nom_client or cabinet.nom

        # Sans dossier fournisseur suivi, ne pas choisir arbitrairement un achat.
        _marquer_relation_cabinet(
            donnees,
            cabinet,
            role_cabinet="client",
            traitement_cabinet_propre=True,
        )
        donnees["direction_a_verifier"] = True
        return None, None, nom_fournisseur

    if fournisseur_est_cabinet and client_est_cabinet:
        # Cas incohérent d'extraction : ne jamais inventer un dossier.
        if cabinet is not None:
            _marquer_relation_cabinet(
                donnees,
                cabinet,
                role_cabinet="ambigu",
                traitement_cabinet_propre=True,
            )
        donnees["direction_a_verifier"] = True
        return None, None, None

    # ========================================================
    # FACTURES NORMALES ENTRE ENTREPRISES / TIERS
    # ========================================================

    if fournisseur is not None and client is None:
        return fournisseur, "ventes", nom_client

    if client is not None and fournisseur is None:
        return client, "achats", nom_fournisseur

    if fournisseur is not None and client is not None:
        # Deux dossiers suivis apparaissent sur la même facture. On ne force
        # pas arbitrairement achat/vente : le document doit être vérifié.
        donnees["direction_a_verifier"] = True
        return fournisseur, None, nom_client

    # Aucun dossier suivi reconnu : on garde le document dans le dossier
    # technique et on laisse la catégorie en vérification.
    donnees["direction_a_verifier"] = True
    entreprise = _obtenir_placeholder(db, cabinet_id)
    return entreprise, None, nom_client or nom_fournisseur
