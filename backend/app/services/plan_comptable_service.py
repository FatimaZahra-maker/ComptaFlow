"""app/services/plan_comptable_service.py

Résolution des comptes exacts du plan comptable d'une entreprise.

Règles de sécurité :
- toujours filtrer cabinet_id + entreprise_id ;
- ne jamais inventer un numéro de compte ;
- en cas de plusieurs candidats plausibles, retourner AMBIGU au lieu de
  choisir arbitrairement.
"""
from __future__ import annotations

from dataclasses import dataclass
import unicodedata
import uuid

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models.compte_comptable_entreprise import CompteComptableEntreprise


USAGES_AUTORISES = {
    "ht",
    "tva",
    "fournisseur",
    "client",
    "banque",
    "gain_change",
    "perte_change",
    "autre",
}


@dataclass(frozen=True)
class ResolutionCompte:
    compte: str | None
    statut: str
    candidats: tuple[str, ...] = ()


def normaliser_numero_compte(valeur: object | None) -> str | None:
    if valeur is None:
        return None
    propre = "".join(
        caractere
        for caractere in str(valeur).strip()
        if caractere.isdigit()
    )
    return propre or None


def normaliser_famille_cgnc(valeur: object | None) -> str | None:
    return normaliser_numero_compte(valeur)


def normaliser_texte(valeur: object | None) -> str | None:
    if valeur is None:
        return None

    texte = str(valeur).strip().lower()
    texte = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texte)
        if not unicodedata.combining(caractere)
    )

    for caractere in ("-", "/", "\\", ".", ",", ";", ":", "(", ")"):
        texte = texte.replace(caractere, " ")

    propre = "_".join(texte.split())
    return propre or None


def normaliser_tiers(valeur: object | None) -> str | None:
    if valeur is None:
        return None

    texte = str(valeur).strip().upper()
    texte = "".join(
        caractere
        for caractere in unicodedata.normalize("NFKD", texte)
        if not unicodedata.combining(caractere)
    )
    propre = " ".join(texte.split())
    return propre or None


def _usage_propre(valeur: object | None) -> str:
    usage = str(valeur or "autre").strip().lower()
    return usage if usage in USAGES_AUTORISES else "autre"


def valider_coherence_compte(
    numero_compte: object,
    famille_cgnc: object | None,
) -> tuple[str, str | None]:
    numero = normaliser_numero_compte(numero_compte)
    famille = normaliser_famille_cgnc(famille_cgnc)

    if numero is None or len(numero) < 3:
        raise ValueError("Numéro de compte invalide.")

    if famille and not numero.startswith(famille):
        raise ValueError(
            f"Le compte {numero} n'appartient pas à la famille {famille}."
        )

    return numero, famille


def creer_ou_mettre_a_jour_compte(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    numero_compte: str,
    libelle: str,
    famille_cgnc: str | None = None,
    type_usage: str = "autre",
    nature_comptable: str | None = None,
    tiers_nom: str | None = None,
    est_divers: bool = False,
    is_active: bool = True,
    source: str = "manuel",
) -> tuple[CompteComptableEntreprise, bool]:
    numero, famille = valider_coherence_compte(
        numero_compte,
        famille_cgnc,
    )

    usage = _usage_propre(type_usage)
    tiers_propre = " ".join(str(tiers_nom or "").strip().split()) or None
    tiers_normalise = normaliser_tiers(tiers_propre)
    nature = normaliser_texte(nature_comptable)
    libelle_propre = " ".join(str(libelle).strip().split())

    if not libelle_propre:
        raise ValueError("Le libellé du compte est obligatoire.")

    compte = (
        db.query(CompteComptableEntreprise)
        .filter(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.numero_compte == numero,
        )
        .first()
    )

    cree = compte is None

    if compte is None:
        compte = CompteComptableEntreprise(
            cabinet_id=cabinet_id,
            entreprise_id=entreprise_id,
            numero_compte=numero,
            libelle=libelle_propre,
        )
        db.add(compte)

    compte.libelle = libelle_propre
    compte.famille_cgnc = famille
    compte.type_usage = usage
    compte.nature_comptable = nature
    compte.tiers_nom = tiers_propre
    compte.tiers_normalise = tiers_normalise
    compte.est_divers = bool(est_divers)
    compte.is_active = bool(is_active)
    compte.source = str(source or "manuel")[:50]

    return compte, cree


def resoudre_compte_par_famille(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    famille_cgnc: str,
    type_usage: str,
    nature_comptable: str | None = None,
) -> ResolutionCompte:
    famille = normaliser_famille_cgnc(famille_cgnc)
    if not famille:
        return ResolutionCompte(None, "famille_invalide")

    usage = _usage_propre(type_usage)
    nature = normaliser_texte(nature_comptable)

    candidats = (
        db.query(CompteComptableEntreprise)
        .filter(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.is_active.is_(True),
            or_(
                CompteComptableEntreprise.famille_cgnc == famille,
                CompteComptableEntreprise.numero_compte.like(f"{famille}%"),
            ),
        )
        .order_by(CompteComptableEntreprise.numero_compte.asc())
        .all()
    )

    if not candidats:
        return ResolutionCompte(None, "introuvable")

    # Priorité à l'usage exact. Les comptes « autre » restent utilisables
    # lorsqu'un plan importé n'a pas encore été enrichi.
    usage_exacts = [c for c in candidats if c.type_usage == usage]
    if usage_exacts:
        candidats = usage_exacts
    else:
        generiques = [c for c in candidats if c.type_usage == "autre"]
        if generiques:
            candidats = generiques

    if nature:
        nature_exacts = [
            c
            for c in candidats
            if normaliser_texte(c.nature_comptable) == nature
        ]
        if len(nature_exacts) == 1:
            return ResolutionCompte(
                nature_exacts[0].numero_compte,
                "trouve_nature",
                (nature_exacts[0].numero_compte,),
            )
        if len(nature_exacts) > 1:
            return ResolutionCompte(
                None,
                "ambigu",
                tuple(c.numero_compte for c in nature_exacts),
            )

    # Ne jamais utiliser un compte DIVERS comme compte HT/TVA exact.
    candidats = [c for c in candidats if not c.est_divers]

    if len(candidats) == 1:
        return ResolutionCompte(
            candidats[0].numero_compte,
            "trouve",
            (candidats[0].numero_compte,),
        )

    if len(candidats) > 1:
        return ResolutionCompte(
            None,
            "ambigu",
            tuple(c.numero_compte for c in candidats),
        )

    return ResolutionCompte(None, "introuvable")


def chercher_compte_tiers(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    tiers: str | None,
    type_usage: str,
) -> ResolutionCompte:
    tiers_normalise = normaliser_tiers(tiers)
    usage = _usage_propre(type_usage)

    if not tiers_normalise or usage not in {"fournisseur", "client"}:
        return ResolutionCompte(None, "tiers_invalide")

    candidats = (
        db.query(CompteComptableEntreprise)
        .filter(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.is_active.is_(True),
            CompteComptableEntreprise.type_usage == usage,
            CompteComptableEntreprise.tiers_normalise == tiers_normalise,
            CompteComptableEntreprise.est_divers.is_(False),
        )
        .order_by(CompteComptableEntreprise.numero_compte.asc())
        .all()
    )

    if len(candidats) == 1:
        return ResolutionCompte(
            candidats[0].numero_compte,
            "trouve",
            (candidats[0].numero_compte,),
        )

    if len(candidats) > 1:
        return ResolutionCompte(
            None,
            "ambigu",
            tuple(c.numero_compte for c in candidats),
        )

    return ResolutionCompte(None, "introuvable")


def chercher_compte_divers(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    type_usage: str,
) -> ResolutionCompte:
    usage = _usage_propre(type_usage)

    if usage not in {"fournisseur", "client"}:
        return ResolutionCompte(None, "usage_invalide")

    candidats = (
        db.query(CompteComptableEntreprise)
        .filter(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.is_active.is_(True),
            CompteComptableEntreprise.type_usage == usage,
            CompteComptableEntreprise.est_divers.is_(True),
        )
        .order_by(CompteComptableEntreprise.numero_compte.asc())
        .all()
    )

    if len(candidats) == 1:
        return ResolutionCompte(
            candidats[0].numero_compte,
            "trouve",
            (candidats[0].numero_compte,),
        )

    if len(candidats) > 1:
        return ResolutionCompte(
            None,
            "ambigu",
            tuple(c.numero_compte for c in candidats),
        )

    return ResolutionCompte(None, "introuvable")


def chercher_compte_usage_unique(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    type_usage: str,
) -> ResolutionCompte:
    """Retourne un compte exact si un seul compte actif possède cet usage.

    Utilisé notamment pour type_usage="banque". Si plusieurs comptes
    bancaires existent, le moteur refuse de deviner lequel correspond au
    relevé et retourne AMBIGU.
    """
    usage = _usage_propre(type_usage)

    candidats = (
        db.query(CompteComptableEntreprise)
        .filter(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.is_active.is_(True),
            CompteComptableEntreprise.type_usage == usage,
        )
        .order_by(CompteComptableEntreprise.numero_compte.asc())
        .all()
    )

    if len(candidats) == 1:
        return ResolutionCompte(
            candidats[0].numero_compte,
            "trouve",
            (candidats[0].numero_compte,),
        )

    if len(candidats) > 1:
        return ResolutionCompte(
            None,
            "ambigu",
            tuple(c.numero_compte for c in candidats),
        )

    return ResolutionCompte(None, "introuvable")
