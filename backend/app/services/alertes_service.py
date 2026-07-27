"""
app/services/alertes_service.py

Calcule les 2 types d'alertes automatiques de la page Rappels & Tâches :

1. lister_ecritures_non_saisies :
   écritures VALIDÉES dont saisie_topaze est encore False -- le
   comptable doit encore les ressaisir dans le logiciel externe.

2. lister_entreprises_en_retard :
   pour chaque entreprise, on établit un "délai de référence" = l'écart
   entre son 1er et son 2e document uploadé (règle métier définie par
   l'utilisateur : on compare le rythme habituel de cette entreprise à
   elle-même, pas à une règle générale du cabinet). Si le temps écoulé
   depuis le DERNIER upload dépasse ce délai de référence, l'entreprise
   est considérée en retard.

   Limite connue (documentée, pas cachée) : une entreprise avec moins de
   2 documents au total n'a pas de délai de référence calculable -- elle
   est simplement exclue de la liste, pas comptée "en retard" par défaut.
"""
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import StatutValidationEnum
from app.schemas.rappel import EcritureNonSaisieOut, EntrepriseRetardOut

SECONDES_PAR_JOUR = 86400


def lister_ecritures_non_saisies(
    db: Session, cabinet_id: uuid.UUID
) -> list[EcritureNonSaisieOut]:
    """Écritures validées non encore marquées 'saisie_topaze'."""
    resultats = db.execute(
        select(EcritureComptable, Document.nom_fichier_original, Entreprise.nom)
        .join(Document, EcritureComptable.document_id == Document.id)
        .join(Entreprise, EcritureComptable.entreprise_id == Entreprise.id)
        .where(
            EcritureComptable.cabinet_id == cabinet_id,
            EcritureComptable.statut_validation == StatutValidationEnum.VALIDE,
            EcritureComptable.saisie_topaze.is_(False),
        )
        .order_by(EcritureComptable.date_piece)
    ).all()

    sortie: list[EcritureNonSaisieOut] = []
    for ecriture, nom_fichier, nom_entreprise in resultats:
        sortie.append(EcritureNonSaisieOut(
            id=ecriture.id,
            entreprise_id=ecriture.entreprise_id,
            entreprise_nom=nom_entreprise,
            document_id=ecriture.document_id,
            nom_fichier_document=nom_fichier,
            tiers=ecriture.tiers,
            numero_piece=ecriture.numero_piece,
            date_piece=ecriture.date_piece,
            montant_ttc=ecriture.montant_ttc,
        ))
    return sortie


def lister_entreprises_en_retard(
    db: Session, cabinet_id: uuid.UUID
) -> list[EntrepriseRetardOut]:
    """Entreprises dont le rythme d'envoi habituel (1er → 2e upload) est dépassé."""
    entreprises = db.execute(
        select(Entreprise).where(
            Entreprise.cabinet_id == cabinet_id,
            Entreprise.is_active.is_(True),
        )
    ).scalars().all()

    maintenant = datetime.utcnow()
    resultats: list[EntrepriseRetardOut] = []

    for entreprise in entreprises:
        dates_upload = db.execute(
            select(Document.created_at)
            .where(
                Document.cabinet_id == cabinet_id,
                Document.entreprise_id == entreprise.id,
            )
            .order_by(Document.created_at.asc())
        ).scalars().all()

        # Il faut au moins 2 documents pour établir un délai de référence
        # (l'écart entre le 1er et le 2e). En dessous, impossible de
        # savoir ce qui est "normal" pour cette entreprise -> on l'ignore.
        if len(dates_upload) < 2:
            continue

        delai_reference = dates_upload[1] - dates_upload[0]
        dernier_upload = dates_upload[-1]
        temps_ecoule = maintenant - dernier_upload

        if temps_ecoule > delai_reference:
            delai_reference_jours = delai_reference.total_seconds() / SECONDES_PAR_JOUR
            jours_ecoules = temps_ecoule.total_seconds() / SECONDES_PAR_JOUR
            resultats.append(EntrepriseRetardOut(
                entreprise_id=entreprise.id,
                entreprise_nom=entreprise.nom,
                dernier_upload=dernier_upload,
                delai_reference_jours=round(delai_reference_jours, 1),
                jours_depuis_dernier_upload=round(jours_ecoules, 1),
                jours_de_retard=round(jours_ecoules - delai_reference_jours, 1),
            ))

    # Les plus en retard en premier
    resultats.sort(key=lambda r: r.jours_de_retard, reverse=True)
    return resultats