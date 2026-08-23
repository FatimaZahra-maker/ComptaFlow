"""
app/services/anomaly_service.py

Détection des doublons comptables de ComptaFlow.

Deux niveaux sont conservés :

1. Doublon métier FORT au niveau Document, AVANT chrono/écriture.
   Une facture déjà connue ne doit pas créer une nouvelle écriture.

2. Doublon potentiel au niveau EcritureComptable, conservé comme garde-fou
   historique pour les cas moins certains.

Le doublon métier est volontairement strict : on exige le même numéro de
pièce et au moins deux confirmations parmi date, TTC et tiers. L'objectif est
d'empêcher une double comptabilisation sans transformer des factures seulement
ressemblantes en faux doublons.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import StatutDocumentEnum

_TOLERANCE_JOURS = 3
_TOLERANCE_MONTANT = Decimal("0.01")


def _premiere_valeur(donnees: dict | None, *cles: str) -> Any:
    if not isinstance(donnees, dict):
        return None
    for cle in cles:
        valeur = donnees.get(cle)
        if valeur not in (None, ""):
            return valeur
    return None


def _normaliser_texte(valeur: Any) -> str | None:
    if valeur in (None, ""):
        return None
    texte = str(valeur).strip().upper()
    if not texte:
        return None
    texte = "".join(
        caractere
        for caractere in unicodedata.normalize("NFD", texte)
        if unicodedata.category(caractere) != "Mn"
    )
    texte = re.sub(r"\b(SARL|SA|SAS|SASU|SNC|STE|SOCIETE|ETS|ETABLISSEMENTS)\b", " ", texte)
    texte = re.sub(r"[^A-Z0-9]+", " ", texte)
    texte = re.sub(r"\s+", " ", texte).strip()
    return texte or None


def _normaliser_numero_piece(valeur: Any) -> str | None:
    texte = _normaliser_texte(valeur)
    if not texte:
        return None
    return re.sub(r"[^A-Z0-9]", "", texte) or None


def _normaliser_date(valeur: Any) -> date | None:
    if valeur in (None, ""):
        return None
    if isinstance(valeur, datetime):
        return valeur.date()
    if isinstance(valeur, date):
        return valeur

    texte = str(valeur).strip()
    for format_date in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y", "%d.%m.%Y"):
        try:
            return datetime.strptime(texte, format_date).date()
        except ValueError:
            continue
    return None


def _normaliser_montant(valeur: Any) -> Decimal | None:
    if valeur in (None, ""):
        return None
    if isinstance(valeur, Decimal):
        return valeur.quantize(Decimal("0.01"))

    texte = str(valeur).strip().replace("\u00a0", "").replace(" ", "")
    if not texte:
        return None

    if "," in texte and "." in texte:
        if texte.rfind(",") > texte.rfind("."):
            texte = texte.replace(".", "").replace(",", ".")
        else:
            texte = texte.replace(",", "")
    elif "," in texte:
        texte = texte.replace(",", ".")

    texte = re.sub(r"[^0-9.\-]", "", texte)
    if not texte:
        return None

    try:
        return Decimal(texte).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None


def _extraire_identite_metier(donnees: dict | None) -> dict[str, Any]:
    numero_piece = _normaliser_numero_piece(
        _premiere_valeur(
            donnees,
            "numero_piece",
            "numero_facture",
            "facture_numero",
            "invoice_number",
        )
    )

    date_piece = _normaliser_date(
        _premiere_valeur(
            donnees,
            "date_piece",
            "date_facture",
            "date",
        )
    )

    montant_ttc = _normaliser_montant(
        _premiere_valeur(
            donnees,
            "montant_ttc",
            "ttc",
            "total_ttc",
        )
    )

    tiers = _normaliser_texte(
        _premiere_valeur(
            donnees,
            "tiers",
            "nom_fournisseur",
            "fournisseur",
            "nom_client",
            "client",
        )
    )

    return {
        "numero_piece": numero_piece,
        "date_piece": date_piece,
        "montant_ttc": montant_ttc,
        "tiers": tiers,
    }


def _montants_egaux(a: Decimal | None, b: Decimal | None) -> bool:
    if a is None or b is None:
        return False
    return abs(a - b) <= _TOLERANCE_MONTANT


def _est_doublon_metier_fort(nouveau: dict, existant: dict) -> bool:
    """
    Règle volontairement prudente.

    Le numéro de pièce est obligatoire pour BLOQUER automatiquement.
    Ensuite, au moins deux éléments parmi date / TTC / tiers doivent confirmer.
    """
    nouveau_id = _extraire_identite_metier(nouveau)
    existant_id = _extraire_identite_metier(existant)

    if not nouveau_id["numero_piece"] or not existant_id["numero_piece"]:
        return False

    if nouveau_id["numero_piece"] != existant_id["numero_piece"]:
        return False

    confirmations = 0

    if (
        nouveau_id["date_piece"] is not None
        and existant_id["date_piece"] is not None
        and nouveau_id["date_piece"] == existant_id["date_piece"]
    ):
        confirmations += 1

    if _montants_egaux(nouveau_id["montant_ttc"], existant_id["montant_ttc"]):
        confirmations += 1

    if (
        nouveau_id["tiers"] is not None
        and existant_id["tiers"] is not None
        and nouveau_id["tiers"] == existant_id["tiers"]
    ):
        confirmations += 1

    return confirmations >= 2


def trouver_document_doublon_metier(
    db: Session,
    document: Document,
    entreprise_id,
    donnees: dict,
) -> Document | None:
    """
    Cherche une facture déjà traitée dans le même dossier comptable.

    Le périmètre est toujours : cabinet_id + entreprise_id. Pour une facture
    propre au cabinet, entreprise_id vaut None et on exige en plus le marqueur
    ``traitement_cabinet_propre`` pour ne jamais mélanger un document non
    rattaché avec la comptabilité propre de SEGURIBAT.

    Cette recherche arrive APRES extraction + identification mais AVANT chrono
    + écriture comptable.
    """
    scope_cabinet_propre = bool(
        donnees.get("traitement_cabinet_propre")
        if isinstance(donnees, dict)
        else False
    )

    candidats = (
        db.query(Document)
        .filter(
            Document.id != document.id,
            Document.cabinet_id == document.cabinet_id,
            Document.entreprise_id == entreprise_id,
            Document.statut.in_(
                [
                    StatutDocumentEnum.TRAITE,
                    StatutDocumentEnum.VALIDE,
                ]
            ),
        )
        .order_by(Document.created_at.desc())
        .limit(500)
        .all()
    )

    for candidat in candidats:
        if candidat.est_doublon:
            continue

        donnees_candidat = candidat.donnees_extraites or {}
        candidat_cabinet_propre = bool(
            donnees_candidat.get("traitement_cabinet_propre")
            if isinstance(donnees_candidat, dict)
            else False
        )

        if candidat_cabinet_propre != scope_cabinet_propre:
            continue

        if _est_doublon_metier_fort(donnees, donnees_candidat):
            return candidat

    return None


def marquer_document_comme_doublon(
    db: Session,
    document: Document,
    document_original: Document,
    donnees: dict,
) -> None:
    """
    Marque le nouvel upload comme doublon SANS créer chrono ni écriture.

    On conserve le fichier uploadé pour traçabilité, mais son JSON indique
    explicitement le document comptable original.
    """
    donnees_enrichies = dict(donnees or {})
    donnees_enrichies["est_doublon"] = True
    donnees_enrichies["doublon_de_document_id"] = str(document_original.id)
    donnees_enrichies["doublon_raison"] = (
        "Même numéro de pièce avec au moins deux confirmations parmi "
        "date, montant TTC et tiers. Aucune nouvelle écriture créée."
    )

    document.donnees_extraites = donnees_enrichies
    document.entreprise_id = document_original.entreprise_id
    document.chrono_id = None
    document.annee = document_original.annee
    document.mois = document_original.mois
    document.categorie = document_original.categorie
    document.statut = StatutDocumentEnum.TRAITE
    document.message_erreur = None
    document.type_erreur = None
    document.error_code = None
    document.saisie_topaze = False

    db.commit()
    db.refresh(document)


def appliquer_detection_doublon(db: Session, ecriture: EcritureComptable) -> None:
    """
    Garde-fou historique pour les doublons POTENTIELS d'écritures.

    Contrairement au doublon métier fort ci-dessus, cette fonction ne bloque
    pas la création ; elle signale seulement l'écriture pour vérification.
    """
    if not ecriture.tiers or not ecriture.date_piece:
        return

    borne_min = ecriture.date_piece - timedelta(days=_TOLERANCE_JOURS)
    borne_max = ecriture.date_piece + timedelta(days=_TOLERANCE_JOURS)

    candidat = (
        db.query(EcritureComptable)
        .filter(
            and_(
                EcritureComptable.id != ecriture.id,
                EcritureComptable.entreprise_id == ecriture.entreprise_id,
                EcritureComptable.tiers == ecriture.tiers,
                EcritureComptable.montant_ttc == ecriture.montant_ttc,
                EcritureComptable.date_piece >= borne_min,
                EcritureComptable.date_piece <= borne_max,
            )
        )
        .first()
    )

    if candidat is not None:
        ecriture.doublon_potentiel_id = candidat.id
        ecriture.anomalie_detectee = True
        message_doublon = f"Doublon potentiel avec l'écriture {candidat.id}."
        ecriture.anomalie_details = (
            f"{ecriture.anomalie_details} | {message_doublon}"
            if ecriture.anomalie_details
            else message_doublon
        )
        db.commit()
