"""Agregateur dynamique des controles techniques de pre-cloture V1.

Le score part de 100 et retranche une penalite par anomalie : 25 points pour
un blocage, 10 pour une anomalie importante, 4 pour un avertissement et 1
pour une information. Le resultat est borne entre 0 et 100. Ces poids sont
volontairement differents et deterministes. Un score de 100 signifie seulement
qu'aucun controle technique connu n'a remonte d'anomalie ; il ne certifie ni
les comptes, ni une declaration fiscale.

Ce service est en lecture seule : il ne cree aucun compte, taux, ligne ou
correction et ne persiste aucun score.
"""
from __future__ import annotations

import uuid
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models.compte_bancaire_entreprise import CompteBancaireEntreprise
from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import StatutDocumentEnum, StatutValidationEnum, TypeEcritureEnum
from app.models.entreprise import Entreprise
from app.models.ligne_comptable import LigneComptable
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.models.regularisation_cloture import RegularisationCloture
from app.models.tva_periode import (
    TvaConfigurationEntreprise, TvaCreditUtilisation, TvaPeriode, TvaRegularisation,
)
from app.services import bilan_service, cpc_service, tva_comptable_service
from app.services.etat_comptable_service import MONEY, ZERO, controler_lignes_validees, decimal_exploitable
from app.services.plan_comptable_service import normaliser_texte

NIVEAUX = ("bloquant", "important", "avertissement", "information")
PRIORITE_NIVEAU = {niveau: index for index, niveau in enumerate(NIVEAUX)}
PENALITES = {"bloquant": 25, "important": 10, "avertissement": 4, "information": 1}
MODULES = (
    "documents", "ecritures", "banque", "devises", "tva", "cloture",
    "grand_livre_balance", "cpc", "bilan",
)


@dataclass(slots=True)
class AnomalieControle:
    code: str
    module: str
    niveau: str
    titre: str
    description: str
    entreprise_id: uuid.UUID
    exercice: int
    objet_type: str
    objet_id: uuid.UUID | None = None
    route_frontend: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ResumeModuleControle:
    module: str
    statut: str
    total_anomalies: int
    bloquants: int
    importants: int
    avertissements: int
    informations: int


@dataclass(slots=True)
class PreClotureResultat:
    entreprise_id: uuid.UUID
    exercice: int
    score: int
    statut: str
    resume: dict[str, ResumeModuleControle]
    anomalies: list[AnomalieControle]
    avertissement_score: str = (
        "Indicateur technique uniquement : ce score ne certifie ni les comptes ni une declaration fiscale."
    )
    source_calcul: str = "controles_dynamiques_donnees_validees"


@dataclass(slots=True)
class PreClotureSnapshot:
    cabinet_id: uuid.UUID
    entreprise_id: uuid.UUID
    exercice: int
    documents: list[object] = field(default_factory=list)
    ecritures: list[object] = field(default_factory=list)
    lignes: list[object] = field(default_factory=list)
    mouvements: list[object] = field(default_factory=list)
    allocations: list[object] = field(default_factory=list)
    comptes_bancaires: list[object] = field(default_factory=list)
    comptes_plan: list[object] = field(default_factory=list)
    tva_configuration: object | None = None
    tva_periodes: list[object] = field(default_factory=list)
    tva_regularisations: list[object] = field(default_factory=list)
    tva_credits: list[object] = field(default_factory=list)
    clotures: list[object] = field(default_factory=list)


def _value(value: object | None) -> str:
    raw = getattr(value, "value", value)
    return str(raw or "").strip().lower()


def _money(value: object | None) -> Decimal:
    try:
        result = Decimal(str(value))
        return result.quantize(MONEY) if result.is_finite() else ZERO
    except (InvalidOperation, ValueError, TypeError):
        return ZERO


def _id(value: object) -> uuid.UUID | None:
    candidate = getattr(value, "id", None)
    return candidate if isinstance(candidate, uuid.UUID) else None


def _scope(items: Iterable[object], snapshot: PreClotureSnapshot, *, entreprise_none: bool = False) -> list[object]:
    return [
        item for item in items
        if getattr(item, "cabinet_id", snapshot.cabinet_id) == snapshot.cabinet_id
        and (
            getattr(item, "entreprise_id", snapshot.entreprise_id) == snapshot.entreprise_id
            or (entreprise_none and getattr(item, "entreprise_id", snapshot.entreprise_id) is None)
        )
    ]


def _annee(value: object | None) -> int | None:
    return value.year if isinstance(value, date) else None


def _anomalie(
    snapshot: PreClotureSnapshot,
    *, code: str, module: str, niveau: str, titre: str, description: str,
    objet_type: str, objet: object | None = None, route: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> AnomalieControle:
    if niveau not in NIVEAUX:
        raise ValueError(f"Niveau de controle inconnu: {niveau}")
    return AnomalieControle(
        code=code, module=module, niveau=niveau, titre=titre, description=description,
        entreprise_id=snapshot.entreprise_id, exercice=snapshot.exercice,
        objet_type=objet_type, objet_id=_id(objet) if objet is not None else None,
        route_frontend=route, metadata=dict(metadata or {}),
    )


def _premiere(data: dict, *keys: str) -> object | None:
    for key in keys:
        if data.get(key) not in (None, ""):
            return data[key]
    return None


def _documents(snapshot: PreClotureSnapshot, ecritures: list[object], mouvements: list[object]) -> list[AnomalieControle]:
    anomalies: list[AnomalieControle] = []
    entries_by_doc: dict[object, list[object]] = defaultdict(list)
    movements_by_doc: dict[object, list[object]] = defaultdict(list)
    for entry in ecritures:
        entries_by_doc[getattr(entry, "document_id", None)].append(entry)
    for movement in mouvements:
        movements_by_doc[getattr(movement, "document_id", None)].append(movement)

    for document in _scope(snapshot.documents, snapshot, entreprise_none=True):
        doc_year = getattr(document, "annee", None)
        if doc_year not in (None, snapshot.exercice):
            continue
        route = f"/documents/{_id(document)}" if _id(document) else "/upload"
        status = _value(getattr(document, "statut", None))
        data = getattr(document, "donnees_extraites", None)
        data = data if isinstance(data, dict) else {}
        if getattr(document, "entreprise_id", None) is None:
            anomalies.append(_anomalie(snapshot, code="document_entreprise_absente", module="documents", niveau="important", titre="Entreprise non identifiee", description="Le document ne peut pas etre rattache de facon sure a une entreprise.", objet_type="document", objet=document, route=route, metadata={"portee": "cabinet_non_attribue"}))
        if status == StatutDocumentEnum.ERREUR.value:
            anomalies.append(_anomalie(snapshot, code="document_erreur", module="documents", niveau="important", titre="Document en erreur", description="Le traitement du document a echoue et requiert une intervention.", objet_type="document", objet=document, route=route, metadata={"error_code": getattr(document, "error_code", None)}))
        elif status in {StatutDocumentEnum.EN_ATTENTE.value, StatutDocumentEnum.EN_TRAITEMENT.value}:
            anomalies.append(_anomalie(snapshot, code="document_traitement_incomplet", module="documents", niveau="avertissement", titre="Document encore en traitement", description="Le document n'est pas encore disponible pour la cloture.", objet_type="document", objet=document, route=route, metadata={"statut": status}))
        if bool(data.get("a_verifier")):
            anomalies.append(_anomalie(snapshot, code="document_a_verifier", module="documents", niveau="important", titre="Document a verifier", description="Le pipeline documentaire a marque ce document pour verification.", objet_type="document", objet=document, route=route))
        if bool(data.get("est_doublon")):
            anomalies.append(_anomalie(snapshot, code="document_doublon", module="documents", niveau="avertissement", titre="Doublon detecte", description="Le document est rattache a un original deja connu.", objet_type="document", objet=document, route=route, metadata={"document_original_id": str(data.get("doublon_de_document_id") or "")}))
        category = _value(getattr(document, "categorie", None))
        if not category:
            anomalies.append(_anomalie(snapshot, code="document_categorie_absente", module="documents", niveau="important", titre="Nature documentaire non identifiee", description="Achat, vente, banque ou autre categorie n'a pas ete determinee.", objet_type="document", objet=document, route=route))
        invoice_category = category in {"achats", "ventes", "fournisseurs", "clients"}
        if invoice_category and not entries_by_doc.get(_id(document)):
            anomalies.append(_anomalie(snapshot, code="document_ecriture_absente", module="documents", niveau="important", titre="Ecriture absente", description="Une piece Achat/Vente ne possede aucune ecriture comptable.", objet_type="document", objet=document, route=route))
        if category == "banque" and not movements_by_doc.get(_id(document)):
            anomalies.append(_anomalie(snapshot, code="document_mouvement_absent", module="documents", niveau="important", titre="Mouvement bancaire absent", description="Un document Banque ne contient aucun mouvement exploitable.", objet_type="document", objet=document, route=route))
        if invoice_category:
            missing = []
            if _premiere(data, "numero_piece", "numero_facture", "facture_numero") is None: missing.append("numero_piece")
            if _premiere(data, "date_piece", "date_facture", "date") is None: missing.append("date_piece")
            if _premiere(data, "montant_ttc", "ttc", "total_ttc") is None: missing.append("montant_ttc")
            if missing:
                anomalies.append(_anomalie(snapshot, code="document_donnees_essentielles_manquantes", module="documents", niveau="important", titre="Donnees essentielles manquantes", description="La piece ne contient pas toutes les donnees minimales extraites.", objet_type="document", objet=document, route=route, metadata={"champs": missing}))
    return anomalies


def _ecritures_et_lignes(snapshot: PreClotureSnapshot, ecritures: list[object], lignes: list[object]) -> list[AnomalieControle]:
    anomalies: list[AnomalieControle] = []
    lines_by_entry: dict[object, list[object]] = defaultdict(list)
    for line in lignes:
        if getattr(line, "ecriture_id", None) is not None:
            lines_by_entry[getattr(line, "ecriture_id")].append(line)
        if not str(getattr(line, "compte", "") or "").strip():
            anomalies.append(_anomalie(snapshot, code="ligne_compte_absent", module="ecritures", niveau="bloquant", titre="Ligne sans compte", description="Une ligne validee ne porte aucun numero de compte.", objet_type="ligne_comptable", objet=line, route="/grand-livre"))

    for entry in ecritures:
        entry_year = _annee(getattr(entry, "date_piece", None))
        if entry_year not in (None, snapshot.exercice):
            continue
        route = f"/documents/{getattr(entry, 'document_id', '')}" if getattr(entry, "document_id", None) else "/registers"
        status = _value(getattr(entry, "statut_validation", None))
        kind = _value(getattr(entry, "type_ecriture", None))
        entry_lines = [line for line in lines_by_entry.get(_id(entry), []) if bool(getattr(line, "est_validee", False))]
        if status == StatutValidationEnum.VALIDE.value and not entry_lines:
            anomalies.append(_anomalie(snapshot, code="ecriture_validee_sans_lignes", module="ecritures", niveau="bloquant", titre="Ecriture validee sans lignes", description="Une ecriture validee n'alimente pas le Grand Livre.", objet_type="ecriture", objet=entry, route=route))
        if entry_lines:
            debit = sum((_money(getattr(line, "debit", None)) for line in entry_lines), ZERO)
            credit = sum((_money(getattr(line, "credit", None)) for line in entry_lines), ZERO)
            if abs(debit - credit) > MONEY:
                anomalies.append(_anomalie(snapshot, code="ecriture_desequilibree", module="ecritures", niveau="bloquant", titre="Ecriture non equilibree", description=f"Total Debit {debit} different du Credit {credit}.", objet_type="ecriture", objet=entry, route=route, metadata={"debit": str(debit), "credit": str(credit)}))
            if any(_annee(getattr(line, "date_ecriture", None)) != snapshot.exercice for line in entry_lines):
                anomalies.append(_anomalie(snapshot, code="ecriture_exercice_incoherent", module="ecritures", niveau="important", titre="Exercice comptable incoherent", description="Au moins une ligne de l'ecriture porte une date hors de l'exercice de la piece.", objet_type="ecriture", objet=entry, route=route))
        if kind in {TypeEcritureEnum.ACHAT.value, TypeEcritureEnum.VENTE.value}:
            for field_name, code, title in (("compte_ht", "compte_ht_manquant", "Compte HT manquant"), ("compte_tiers", "compte_tiers_manquant", "Compte tiers manquant")):
                if not getattr(entry, field_name, None):
                    anomalies.append(_anomalie(snapshot, code=code, module="ecritures", niveau="bloquant", titre=title, description="Aucun compte exact n'est disponible dans le plan de l'entreprise.", objet_type="ecriture", objet=entry, route=route))
            if _money(getattr(entry, "montant_tva", None)) > ZERO and not getattr(entry, "compte_tva", None):
                anomalies.append(_anomalie(snapshot, code="compte_tva_manquant", module="ecritures", niveau="bloquant", titre="Compte TVA manquant", description="La TVA est positive mais aucun compte TVA exact n'est renseigne.", objet_type="ecriture", objet=entry, route=route))
        if kind == TypeEcritureEnum.BANQUE.value and not getattr(entry, "compte_tiers", None):
            anomalies.append(_anomalie(snapshot, code="compte_bancaire_ecriture_manquant", module="ecritures", niveau="bloquant", titre="Compte bancaire manquant", description="L'ecriture Banque ne possede aucun compte exact.", objet_type="ecriture", objet=entry, route="/banque"))
        if status == StatutValidationEnum.A_VERIFIER.value:
            anomalies.append(_anomalie(snapshot, code="ecriture_a_verifier", module="ecritures", niveau="important", titre="Ecriture a verifier", description="L'ecriture n'est pas validee pour la cloture.", objet_type="ecriture", objet=entry, route=route))
        if getattr(entry, "doublon_potentiel_id", None):
            anomalies.append(_anomalie(snapshot, code="ecriture_doublon_potentiel", module="ecritures", niveau="avertissement", titre="Doublon potentiel", description="Un rapprochement manuel avec l'ecriture similaire est requis.", objet_type="ecriture", objet=entry, route=route, metadata={"doublon_id": str(getattr(entry, "doublon_potentiel_id"))}))
    return anomalies


def _grand_livre_balance(snapshot: PreClotureSnapshot, lignes: list[object], sources_connues: set[object]) -> tuple[list[AnomalieControle], object]:
    current = [line for line in lignes if _annee(getattr(line, "date_ecriture", None)) == snapshot.exercice]
    control = controler_lignes_validees(
        current, cabinet_id=snapshot.cabinet_id, entreprise_id=snapshot.entreprise_id,
        date_debut=date(snapshot.exercice, 1, 1), date_fin=date(snapshot.exercice, 12, 31),
    )
    anomalies = [
        _anomalie(snapshot, code="grand_livre_balance_anomalie", module="grand_livre_balance", niveau="bloquant" if "non equilibrees" in reason or "ne correspondent" in reason else "important", titre="Controle Grand Livre / Balance", description=reason, objet_type="etat", route="/balance")
        for reason in control.anomalies
    ]
    for line in current:
        source_ids = [getattr(line, name, None) for name in ("ecriture_id", "mouvement_bancaire_id", "regularisation_cloture_id")]
        present = [value for value in source_ids if value is not None]
        if len(present) != 1 or present[0] not in sources_connues:
            anomalies.append(_anomalie(snapshot, code="ligne_comptable_orpheline", module="grand_livre_balance", niveau="bloquant", titre="Ligne comptable orpheline", description="La source unique de cette ligne est absente ou hors perimetre.", objet_type="ligne_comptable", objet=line, route="/grand-livre"))
    return anomalies, control


def _banque(
    snapshot: PreClotureSnapshot,
    mouvements: list[object],
    allocations: list[object],
    ecritures: list[object],
) -> list[AnomalieControle]:
    anomalies: list[AnomalieControle] = []
    active_accounts = [item for item in _scope(snapshot.comptes_bancaires, snapshot) if bool(getattr(item, "is_active", True))]
    allocations_by_movement: dict[object, list[object]] = defaultdict(list)
    allocations_by_entry: dict[object, list[object]] = defaultdict(list)
    for allocation in allocations:
        allocations_by_movement[getattr(allocation, "mouvement_bancaire_id", None)].append(allocation)
        allocations_by_entry[getattr(allocation, "ecriture_id", None)].append(allocation)

    for movement in mouvements:
        if _annee(getattr(movement, "date_operation", None)) != snapshot.exercice:
            continue
        status = _value(getattr(movement, "statut_rapprochement", None))
        route = "/banque"
        if status == "non_rapproche":
            anomalies.append(_anomalie(snapshot, code="mouvement_non_rapproche", module="banque", niveau="important", titre="Mouvement non rapproche", description="Le mouvement bancaire n'est rattache a aucune operation comptable.", objet_type="mouvement_bancaire", objet=movement, route=route))
        elif status in {"ambigu", "a_verifier"}:
            anomalies.append(_anomalie(snapshot, code="rapprochement_ambigu", module="banque", niveau="important", titre="Rapprochement ambigu", description="Le rapprochement bancaire requiert une decision humaine.", objet_type="mouvement_bancaire", objet=movement, route=route, metadata={"statut": status}))
        if not getattr(movement, "compte_bancaire_entreprise_id", None) or not str(getattr(movement, "compte_banque", "") or "").strip():
            anomalies.append(_anomalie(snapshot, code="compte_bancaire_non_identifie", module="banque", niveau="bloquant", titre="Compte bancaire non identifie", description="Le compte bancaire exact du mouvement n'est pas determine.", objet_type="mouvement_bancaire", objet=movement, route=route, metadata={"comptes_actifs": len(active_accounts)}))
        if len(active_accounts) > 1 and not getattr(movement, "compte_bancaire_entreprise_id", None):
            anomalies.append(_anomalie(snapshot, code="rib_iban_non_resolu", module="banque", niveau="important", titre="RIB/IBAN non resolu", description="Plusieurs comptes bancaires sont actifs et le releve n'a pas permis d'en identifier un de facon sure.", objet_type="mouvement_bancaire", objet=movement, route=route, metadata={"comptes_actifs": len(active_accounts)}))
        nature = _value(getattr(movement, "nature_operation", None))
        if nature == "virement_interne" and not getattr(movement, "mouvement_lie_id", None):
            anomalies.append(_anomalie(snapshot, code="virement_interne_incomplet", module="banque", niveau="important", titre="Virement interne incomplet", description="Le mouvement oppose n'est pas identifie.", objet_type="mouvement_bancaire", objet=movement, route=route))
        if nature in {"acompte", "frais_bancaire", "autre"} and not str(getattr(movement, "compte_contrepartie", "") or "").strip():
            anomalies.append(_anomalie(snapshot, code="contrepartie_bancaire_manquante", module="banque", niveau="bloquant", titre="Compte de contrepartie manquant", description="Aucun compte exact ne peut etre utilise pour cette operation speciale.", objet_type="mouvement_bancaire", objet=movement, route=route, metadata={"nature": nature}))
        confirmed = [item for item in allocations_by_movement.get(_id(movement), []) if _value(getattr(item, "statut", None)) in {"automatique", "confirme"}]
        if nature == "reglement_facture" and confirmed:
            allocated = sum((_money(getattr(item, "montant_reglement_mad", None) or getattr(item, "montant_affecte", None)) for item in confirmed), ZERO)
            movement_amount = abs(_money(getattr(movement, "montant_mad", None) or getattr(movement, "montant", None)))
            if allocated + MONEY < movement_amount:
                anomalies.append(_anomalie(snapshot, code="mouvement_partiellement_alloue", module="banque", niveau="important", titre="Montant bancaire partiellement alloue", description="Une partie du mouvement reste sans facture rapprochee.", objet_type="mouvement_bancaire", objet=movement, route=route, metadata={"montant": str(movement_amount), "alloue": str(allocated)}))

    for entry in ecritures:
        if _annee(getattr(entry, "date_piece", None)) != snapshot.exercice:
            continue
        confirmed = [item for item in allocations_by_entry.get(_id(entry), []) if _value(getattr(item, "statut", None)) in {"automatique", "confirme"}]
        if not confirmed:
            continue
        allocated = sum((_money(getattr(item, "valeur_comptable_mad", None) or getattr(item, "montant_affecte", None)) for item in confirmed), ZERO)
        total = abs(_money(getattr(entry, "montant_ttc_mad", None) or getattr(entry, "montant_ttc", None)))
        if allocated > total + MONEY:
            anomalies.append(_anomalie(snapshot, code="facture_surallouee", module="banque", niveau="bloquant", titre="Facture sur-allouee", description="Les allocations depassent le montant comptable de la facture.", objet_type="ecriture", objet=entry, route="/banque", metadata={"facture": str(total), "alloue": str(allocated)}))
        elif allocated + MONEY < total:
            anomalies.append(_anomalie(snapshot, code="facture_partiellement_reglee", module="banque", niveau="avertissement", titre="Facture partiellement reglee", description="Le solde restant doit rester suivi sans etre force.", objet_type="ecriture", objet=entry, route="/banque", metadata={"facture": str(total), "alloue": str(allocated)}))
    return anomalies


def _devises(
    snapshot: PreClotureSnapshot,
    ecritures: list[object],
    mouvements: list[object],
    allocations: list[object],
) -> list[AnomalieControle]:
    anomalies: list[AnomalieControle] = []
    entries_by_id = {_id(item): item for item in ecritures}
    movements_by_id = {_id(item): item for item in mouvements}
    for obj, date_name, amount_name, mad_name, rate_name, source_name, object_type, route in [
        *[(entry, "date_piece", "montant_ttc_devise", "montant_ttc_mad", "taux_change_initial", "source_cours_initial", "ecriture", "/registers") for entry in ecritures],
        *[(movement, "date_operation", "montant_devise", "montant_mad", "taux_change", "source_cours_change", "mouvement_bancaire", "/banque") for movement in mouvements],
    ]:
        if _annee(getattr(obj, date_name, None)) != snapshot.exercice or _value(getattr(obj, "devise_originale", "MAD")) in {"", "mad"}:
            continue
        if getattr(obj, amount_name, None) is None:
            anomalies.append(_anomalie(snapshot, code="montant_devise_original_manquant", module="devises", niveau="bloquant", titre="Montant original en devise manquant", description="La valeur originale doit etre conservee sans reconstruction arbitraire.", objet_type=object_type, objet=obj, route=route))
        mad_available = getattr(obj, mad_name, None) is not None or (object_type == "mouvement_bancaire" and getattr(obj, "montant_mad_theorique", None) is not None)
        if not mad_available:
            anomalies.append(_anomalie(snapshot, code="montant_mad_manquant", module="devises", niveau="bloquant", titre="Valeur MAD manquante", description="Aucune valeur MAD reelle ou theorique sure n'est disponible.", objet_type=object_type, objet=obj, route=route))
        if getattr(obj, rate_name, None) is None or not getattr(obj, source_name, None):
            anomalies.append(_anomalie(snapshot, code="cours_change_manquant", module="devises", niveau="important", titre="Cours de change manquant", description="Le cours applicable et sa source ne sont pas tous deux traces.", objet_type=object_type, objet=obj, route=route))

    usages = {_value(getattr(account, "type_usage", None)) for account in _scope(snapshot.comptes_plan, snapshot) if bool(getattr(account, "is_active", True))}
    for allocation in allocations:
        nature = _value(getattr(allocation, "nature_ecart_change", None))
        status = _value(getattr(allocation, "statut_ecart_change", None))
        entry = entries_by_id.get(getattr(allocation, "ecriture_id", None))
        movement = movements_by_id.get(getattr(allocation, "mouvement_bancaire_id", None))
        entry_currency = _value(getattr(entry, "devise_originale", "MAD")) if entry else ""
        movement_currency = _value(getattr(movement, "devise_originale", "MAD")) if movement else ""
        foreign_settlement = entry_currency not in {"", "mad"} or movement_currency not in {"", "mad"}
        if foreign_settlement and status not in {"comptabilise", "non_requis", "a_verifier"}:
            anomalies.append(_anomalie(snapshot, code="reglement_devise_non_traite", module="devises", niveau="important", titre="Reglement en devise non traite", description="Le rapprochement ne porte aucun traitement explicite d'ecart de change.", objet_type="allocation_bancaire", objet=allocation, route="/banque", metadata={"statut_ecart": status or None}))
        if entry_currency and movement_currency and entry_currency != movement_currency:
            anomalies.append(_anomalie(snapshot, code="devises_facture_reglement_incoherentes", module="devises", niveau="important", titre="Devises facture/reglement incoherentes", description="La devise originale du reglement differe de celle de la facture.", objet_type="allocation_bancaire", objet=allocation, route="/banque", metadata={"devise_facture": entry_currency.upper(), "devise_reglement": movement_currency.upper()}))
        if nature == "a_verifier" or status == "a_verifier":
            anomalies.append(_anomalie(snapshot, code="ecart_change_a_verifier", module="devises", niveau="important", titre="Ecart de change a verifier", description=getattr(allocation, "raison_ecart_change", None) or "Le traitement de l'ecart de change n'est pas suffisamment determine.", objet_type="allocation_bancaire", objet=allocation, route="/banque"))
        if nature in {"gain", "perte"} and not str(getattr(allocation, "compte_ecart_change", "") or "").strip():
            anomalies.append(_anomalie(snapshot, code=f"compte_{nature}_change_manquant", module="devises", niveau="bloquant", titre=f"Compte de {nature} de change manquant", description="Aucun compte exact du plan n'a ete identifie.", objet_type="allocation_bancaire", objet=allocation, route="/banque"))
        if nature in {"gain", "perte"} and f"{nature}_change" not in usages:
            anomalies.append(_anomalie(snapshot, code=f"plan_{nature}_change_manquant", module="devises", niveau="bloquant", titre=f"Compte de {nature} absent du plan", description="Le plan actif ne configure aucun compte exact pour cette nature d'ecart.", objet_type="allocation_bancaire", objet=allocation, route="/banque"))
    return anomalies


def _tva(snapshot: PreClotureSnapshot, lignes: list[object], ecritures: list[object]) -> list[AnomalieControle]:
    anomalies: list[AnomalieControle] = []
    current_lines = [line for line in lignes if _annee(getattr(line, "date_ecriture", None)) == snapshot.exercice]
    current_entries = [entry for entry in ecritures if _annee(getattr(entry, "date_piece", None)) == snapshot.exercice and _value(getattr(entry, "statut_validation", None)) == StatutValidationEnum.VALIDE.value]
    synthesis = tva_comptable_service.construire_synthese_tva(entreprise_id=snapshot.entreprise_id, annee=snapshot.exercice, lignes=current_lines, ecritures=current_entries)
    for month in synthesis.mensualites:
        if month.a_verifier:
            anomalies.append(_anomalie(snapshot, code="tva_mois_a_verifier", module="tva", niveau="important", titre=f"TVA {month.mois:02d}/{snapshot.exercice} a verifier", description="; ".join(month.raisons_verification), objet_type="periode_tva", route="/tva-mensuelle", metadata={"mois": month.mois}))
    has_tva = any(month.nombre_lignes_tva or month.tva_collectee or month.tva_deductible for month in synthesis.mensualites)
    config = snapshot.tva_configuration
    if has_tva and (config is None or not getattr(config, "periodicite", None)):
        anomalies.append(_anomalie(snapshot, code="configuration_tva_incomplete", module="tva", niveau="important", titre="Configuration TVA incomplete", description="La periodicite fiscale n'est pas configuree ; aucune regle n'est supposee.", objet_type="configuration_tva", objet=config, route="/tva-mensuelle"))
    if has_tva and config is not None and (getattr(config, "prorata_applicable", None) is None or getattr(config, "retenue_applicable", None) is None):
        anomalies.append(_anomalie(snapshot, code="regle_fiscale_non_configuree", module="tva", niveau="important", titre="Regle fiscale non configuree", description="L'applicabilite du prorata ou de la retenue TVA n'est pas explicitement configuree ; aucun calcul arbitraire n'est effectue.", objet_type="configuration_tva", objet=config, route="/tva-mensuelle"))
    periods = [period for period in _scope(snapshot.tva_periodes, snapshot) if getattr(period, "annee", None) == snapshot.exercice]
    period_ids = {_id(period) for period in periods}
    for period in periods:
        if bool(getattr(period, "a_verifier", False)) or _value(getattr(period, "statut", None)) not in {"validee", "cloturee"}:
            anomalies.append(_anomalie(snapshot, code="periode_tva_non_validable", module="tva", niveau="important", titre="Periode TVA non validee", description="La periode reste provisoire ou porte des anomalies.", objet_type="periode_tva", objet=period, route="/tva-mensuelle", metadata={"mois": getattr(period, "mois", None), "statut": _value(getattr(period, "statut", None))}))
    for regularisation in _scope(snapshot.tva_regularisations, snapshot):
        if getattr(regularisation, "periode_id", None) in period_ids and _value(getattr(regularisation, "statut", None)) != "validee":
            anomalies.append(_anomalie(snapshot, code="regularisation_tva_non_validee", module="tva", niveau="important", titre="Regularisation TVA non validee", description="Une regularisation de la periode n'est pas validee.", objet_type="regularisation_tva", objet=regularisation, route="/tva-mensuelle"))
    source_counts = Counter(getattr(item, "periode_source_id", None) for item in _scope(snapshot.tva_credits, snapshot))
    destination_counts = Counter(getattr(item, "periode_destination_id", None) for item in _scope(snapshot.tva_credits, snapshot))
    if any(key is not None and count > 1 for key, count in source_counts.items()) or any(key is not None and count > 1 for key, count in destination_counts.items()):
        anomalies.append(_anomalie(snapshot, code="credit_tva_double_utilisation", module="tva", niveau="bloquant", titre="Credit TVA utilise plusieurs fois", description="La piste d'audit contient une double utilisation du meme credit ou de la meme destination.", objet_type="credit_tva", route="/tva-mensuelle"))
    all_periods = {_id(period): period for period in _scope(snapshot.tva_periodes, snapshot)}
    credits_by_destination = {getattr(item, "periode_destination_id", None): item for item in _scope(snapshot.tva_credits, snapshot)}
    for period in periods:
        source = all_periods.get(getattr(period, "credit_source_periode_id", None))
        used = credits_by_destination.get(_id(period))
        expected = _money(getattr(source, "credit_a_reporter", None)) if source is not None else ZERO
        declared = _money(getattr(period, "credit_anterieur", None))
        traced = _money(getattr(used, "montant_utilise", None)) if used is not None else ZERO
        if declared > ZERO and (source is None or used is None or abs(declared - expected) > MONEY or abs(declared - traced) > MONEY):
            anomalies.append(_anomalie(snapshot, code="credit_tva_precedent_incoherent", module="tva", niveau="important", titre="Credit TVA precedent incoherent", description="Le credit anterieur ne correspond pas simultanement a sa periode source et a sa piste d'utilisation.", objet_type="periode_tva", objet=period, route="/tva-mensuelle", metadata={"declare": str(declared), "source": str(expected), "utilise": str(traced)}))
    return anomalies


def _cloture(snapshot: PreClotureSnapshot, lignes: list[object]) -> list[AnomalieControle]:
    anomalies: list[AnomalieControle] = []
    lines_by_closure: dict[object, list[object]] = defaultdict(list)
    for line in lignes:
        lines_by_closure[getattr(line, "regularisation_cloture_id", None)].append(line)
    report_sources: Counter = Counter()
    for closure in _scope(snapshot.clotures, snapshot):
        if getattr(closure, "exercice", None) != snapshot.exercice:
            continue
        status = _value(getattr(closure, "statut", None))
        if getattr(closure, "report_source_id", None):
            report_sources[getattr(closure, "report_source_id")] += 1
        if not getattr(closure, "compte_debit", None) or not getattr(closure, "compte_credit", None):
            anomalies.append(_anomalie(snapshot, code="cloture_compte_manquant", module="cloture", niveau="bloquant", titre="Compte de cloture manquant", description="La regularisation ne possede pas les deux comptes exacts requis.", objet_type="regularisation_cloture", objet=closure, route="/cloture"))
        if _annee(getattr(closure, "date_ecriture", None)) not in {None, snapshot.exercice}:
            anomalies.append(_anomalie(snapshot, code="cloture_exercice_incoherent", module="cloture", niveau="important", titre="Exercice de cloture incoherent", description="La date d'ecriture n'appartient pas a l'exercice de la regularisation.", objet_type="regularisation_cloture", objet=closure, route="/cloture"))
        if status in {"validee", "a_verifier"}:
            anomalies.append(_anomalie(snapshot, code="cloture_non_comptabilisee", module="cloture", niveau="important", titre="Regularisation non comptabilisee", description="La regularisation ne produit pas encore de lignes validees dans les etats.", objet_type="regularisation_cloture", objet=closure, route="/cloture", metadata={"statut": status}))
        elif status == "brouillon":
            anomalies.append(_anomalie(snapshot, code="cloture_brouillon", module="cloture", niveau="avertissement", titre="Regularisation en brouillon", description="Une regularisation de cloture reste a instruire.", objet_type="regularisation_cloture", objet=closure, route="/cloture"))
        closure_lines = [line for line in lines_by_closure.get(_id(closure), []) if bool(getattr(line, "est_validee", False))]
        if status == "comptabilisee" and not closure_lines:
            anomalies.append(_anomalie(snapshot, code="cloture_sans_lignes", module="cloture", niveau="bloquant", titre="Cloture comptabilisee sans lignes", description="La regularisation comptabilisee n'alimente pas le Grand Livre.", objet_type="regularisation_cloture", objet=closure, route="/cloture"))
        if closure_lines:
            debit = sum((_money(getattr(line, "debit", None)) for line in closure_lines), ZERO)
            credit = sum((_money(getattr(line, "credit", None)) for line in closure_lines), ZERO)
            if abs(debit - credit) > MONEY:
                anomalies.append(_anomalie(snapshot, code="cloture_lignes_desequilibrees", module="cloture", niveau="bloquant", titre="Lignes de cloture desequilibrees", description="Les lignes Debit/Credit de la regularisation ne s'equilibrent pas.", objet_type="regularisation_cloture", objet=closure, route="/cloture"))
        if bool(getattr(closure, "a_extourner", False)) and getattr(closure, "date_extourne", None) is None:
            anomalies.append(_anomalie(snapshot, code="extourne_non_planifiee", module="cloture", niveau="important", titre="Extourne non planifiee", description="La regularisation doit etre extournee mais aucune date n'est renseignee.", objet_type="regularisation_cloture", objet=closure, route="/cloture"))
    if any(count > 1 for count in report_sources.values()):
        anomalies.append(_anomalie(snapshot, code="report_cloture_duplique", module="cloture", niveau="bloquant", titre="Report a nouveau duplique", description="Une meme cloture source est reportee plusieurs fois.", objet_type="regularisation_cloture", route="/cloture"))
    return anomalies


def calculer_score(anomalies: Iterable[AnomalieControle]) -> int:
    return max(0, 100 - sum(PENALITES[item.niveau] for item in anomalies))


def determiner_statut(anomalies: Iterable[AnomalieControle]) -> str:
    levels = {item.niveau for item in anomalies}
    if "bloquant" in levels:
        return "bloque"
    if "important" in levels:
        return "a_verifier"
    return "pret"


def _etat_cpc_bilan(snapshot: PreClotureSnapshot, lignes: list[object]) -> tuple[list[AnomalieControle], list[AnomalieControle]]:
    valid = [line for line in lignes if bool(getattr(line, "est_validee", False))]
    current = [line for line in valid if _annee(getattr(line, "date_ecriture", None)) == snapshot.exercice]
    previous = [line for line in valid if _annee(getattr(line, "date_ecriture", None)) == snapshot.exercice - 1]
    cumulative = [line for line in valid if isinstance(getattr(line, "date_ecriture", None), date) and getattr(line, "date_ecriture") <= date(snapshot.exercice, 12, 31)]
    labels = {bilan_service.normaliser_compte(getattr(account, "numero_compte", None)): str(getattr(account, "libelle", "") or "") for account in _scope(snapshot.comptes_plan, snapshot) if bool(getattr(account, "is_active", True))}
    labels.pop("", None)
    cpc = cpc_service.calculer_cpc_v2_depuis_lignes(cabinet_id=snapshot.cabinet_id, entreprise_id=snapshot.entreprise_id, exercice=snapshot.exercice, lignes_n=current, lignes_n_1=previous, libelles_comptes=labels)
    cpc_anomalies = [_anomalie(snapshot, code="cpc_compte_non_classe" if "non classe" in reason.lower() or "non reconnu" in reason.lower() else "cpc_anomalie", module="cpc", niveau="important", titre="CPC a verifier", description=reason, objet_type="cpc", route="/cpc") for reason in cpc.anomalies]
    if current and not cpc.donnees_n_1_disponibles:
        cpc_anomalies.append(_anomalie(snapshot, code="cpc_n_1_indisponible", module="cpc", niveau="information", titre="Comparatif N-1 indisponible", description="Aucune donnee de gestion N-1 n'est disponible ; aucune valeur n'est fabriquee.", objet_type="cpc", route="/cpc"))
    result_row = next((item for item in cpc.resultats if item.code == "resultat_net"), None)
    result_net = getattr(result_row, "montant_n", ZERO)
    result_accounts = {bilan_service.normaliser_compte(getattr(account, "numero_compte", None)) for account in _scope(snapshot.comptes_plan, snapshot) if normaliser_texte(getattr(account, "nature_comptable", None)) in {"resultat_exercice", "resultat_net"} and bilan_service.normaliser_compte(getattr(account, "numero_compte", None)).startswith("1")}
    for closure in _scope(snapshot.clotures, snapshot):
        if getattr(closure, "exercice", None) == snapshot.exercice and _value(getattr(closure, "type_regularisation", None)) == "resultat_cloture" and _value(getattr(closure, "statut", None)) == "comptabilisee":
            for name in ("compte_debit", "compte_credit"):
                account = bilan_service.normaliser_compte(getattr(closure, name, None))
                if account.startswith("1"):
                    result_accounts.add(account)
    bilan = bilan_service.calculer_bilan_v2_depuis_lignes(cabinet_id=snapshot.cabinet_id, entreprise_id=snapshot.entreprise_id, exercice=snapshot.exercice, lignes=cumulative, resultat_net_cpc=result_net, comptes_resultat_configures=result_accounts, libelles_comptes=labels, anomalies_cpc=cpc.anomalies)
    bilan_anomalies: list[AnomalieControle] = []
    for reason in bilan.anomalies:
        lowered = reason.lower()
        blocking = "non equilibre" in lowered or "incoherent" in lowered
        code = "bilan_desequilibre" if "non equilibre" in lowered else "resultat_cpc_bilan_incoherent" if "incoherent" in lowered else "bilan_compte_non_classe" if "non classe" in lowered else "bilan_anomalie"
        bilan_anomalies.append(_anomalie(snapshot, code=code, module="bilan", niveau="bloquant" if blocking else "important", titre="Bilan a verifier", description=reason, objet_type="bilan", route="/bilan", metadata={"ecart": str(bilan.ecart)}))
    if bilan.resultat_deja_comptabilise and bilan.resultat_non_affecte != ZERO:
        bilan_anomalies.append(_anomalie(snapshot, code="resultat_bilan_double", module="bilan", niveau="bloquant", titre="Resultat ajoute deux fois", description="Le resultat est simultanement comptabilise et presente comme non affecte.", objet_type="bilan", route="/bilan"))
    return cpc_anomalies, bilan_anomalies


def calculer_precloture_snapshot(snapshot: PreClotureSnapshot) -> PreClotureResultat:
    ecritures = _scope(snapshot.ecritures, snapshot)
    lignes = _scope(snapshot.lignes, snapshot)
    mouvements = _scope(snapshot.mouvements, snapshot)
    allocations = _scope(snapshot.allocations, snapshot)
    clotures = _scope(snapshot.clotures, snapshot)
    sources = {_id(item) for item in [*ecritures, *mouvements, *clotures]}
    sources.discard(None)
    anomalies: list[AnomalieControle] = []
    anomalies.extend(_documents(snapshot, ecritures, mouvements))
    anomalies.extend(_ecritures_et_lignes(snapshot, ecritures, [line for line in lignes if bool(getattr(line, "est_validee", False))]))
    anomalies.extend(_banque(snapshot, mouvements, allocations, ecritures))
    anomalies.extend(_devises(snapshot, ecritures, mouvements, allocations))
    anomalies.extend(_tva(snapshot, [line for line in lignes if bool(getattr(line, "est_validee", False))], ecritures))
    anomalies.extend(_cloture(snapshot, lignes))
    gl_anomalies, _ = _grand_livre_balance(snapshot, [line for line in lignes if bool(getattr(line, "est_validee", False))], sources)
    anomalies.extend(gl_anomalies)
    cpc_anomalies, bilan_anomalies = _etat_cpc_bilan(snapshot, lignes)
    anomalies.extend(cpc_anomalies)
    anomalies.extend(bilan_anomalies)
    unique: dict[tuple, AnomalieControle] = {}
    for anomaly in anomalies:
        key = (anomaly.code, anomaly.module, anomaly.objet_id, anomaly.description)
        unique.setdefault(key, anomaly)
    ordered = sorted(unique.values(), key=lambda item: (PRIORITE_NIVEAU[item.niveau], item.module, item.code, str(item.objet_id or "")))
    resume: dict[str, ResumeModuleControle] = {}
    for module in MODULES:
        selected = [item for item in ordered if item.module == module]
        counts = Counter(item.niveau for item in selected)
        module_status = "bloque" if counts["bloquant"] else "a_verifier" if counts["important"] or counts["avertissement"] else "ok"
        resume[module] = ResumeModuleControle(module=module, statut=module_status, total_anomalies=len(selected), bloquants=counts["bloquant"], importants=counts["important"], avertissements=counts["avertissement"], informations=counts["information"])
    return PreClotureResultat(entreprise_id=snapshot.entreprise_id, exercice=snapshot.exercice, score=calculer_score(ordered), statut=determiner_statut(ordered), resume=resume, anomalies=ordered)


def charger_snapshot(db: Session, *, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID, exercice: int) -> PreClotureSnapshot:
    company = db.execute(select(Entreprise.id).where(Entreprise.id == entreprise_id, Entreprise.cabinet_id == cabinet_id)).scalar_one_or_none()
    if company is None:
        raise ValueError("Entreprise introuvable dans ce cabinet.")
    start_previous = date(exercice - 1, 1, 1)
    end = date(exercice, 12, 31)
    documents = db.execute(select(Document).where(Document.cabinet_id == cabinet_id, or_(Document.entreprise_id == entreprise_id, Document.entreprise_id.is_(None)), or_(Document.annee == exercice, Document.annee.is_(None)))).scalars().all()
    entries = db.execute(select(EcritureComptable).where(EcritureComptable.cabinet_id == cabinet_id, EcritureComptable.entreprise_id == entreprise_id, or_(EcritureComptable.date_piece <= end, EcritureComptable.date_piece.is_(None)))).scalars().all()
    lines = db.execute(select(LigneComptable).where(LigneComptable.cabinet_id == cabinet_id, LigneComptable.entreprise_id == entreprise_id, LigneComptable.date_ecriture <= end)).scalars().all()
    movements = db.execute(select(MouvementBancaire).where(MouvementBancaire.cabinet_id == cabinet_id, MouvementBancaire.entreprise_id == entreprise_id, MouvementBancaire.date_operation <= end)).scalars().all()
    allocations = db.execute(select(RapprochementBancaireAllocation).where(RapprochementBancaireAllocation.cabinet_id == cabinet_id, RapprochementBancaireAllocation.entreprise_id == entreprise_id)).scalars().all()
    bank_accounts = db.execute(select(CompteBancaireEntreprise).where(CompteBancaireEntreprise.cabinet_id == cabinet_id, CompteBancaireEntreprise.entreprise_id == entreprise_id, CompteBancaireEntreprise.is_active.is_(True))).scalars().all()
    plan = db.execute(select(CompteComptableEntreprise).where(CompteComptableEntreprise.cabinet_id == cabinet_id, CompteComptableEntreprise.entreprise_id == entreprise_id, CompteComptableEntreprise.is_active.is_(True))).scalars().all()
    config = db.execute(select(TvaConfigurationEntreprise).where(TvaConfigurationEntreprise.cabinet_id == cabinet_id, TvaConfigurationEntreprise.entreprise_id == entreprise_id)).scalar_one_or_none()
    periods = db.execute(select(TvaPeriode).where(TvaPeriode.cabinet_id == cabinet_id, TvaPeriode.entreprise_id == entreprise_id, TvaPeriode.annee <= exercice)).scalars().all()
    regularisations = db.execute(select(TvaRegularisation).where(TvaRegularisation.cabinet_id == cabinet_id, TvaRegularisation.entreprise_id == entreprise_id, TvaRegularisation.date_regularisation >= start_previous, TvaRegularisation.date_regularisation <= end)).scalars().all()
    credits = db.execute(select(TvaCreditUtilisation).where(TvaCreditUtilisation.cabinet_id == cabinet_id, TvaCreditUtilisation.entreprise_id == entreprise_id)).scalars().all()
    closures = db.execute(select(RegularisationCloture).where(RegularisationCloture.cabinet_id == cabinet_id, RegularisationCloture.entreprise_id == entreprise_id, RegularisationCloture.exercice.in_([exercice - 1, exercice]))).scalars().all()
    return PreClotureSnapshot(cabinet_id=cabinet_id, entreprise_id=entreprise_id, exercice=exercice, documents=list(documents), ecritures=list(entries), lignes=list(lines), mouvements=list(movements), allocations=list(allocations), comptes_bancaires=list(bank_accounts), comptes_plan=list(plan), tva_configuration=config, tva_periodes=list(periods), tva_regularisations=list(regularisations), tva_credits=list(credits), clotures=list(closures))


def calculer_precloture(db: Session, *, cabinet_id: uuid.UUID, entreprise_id: uuid.UUID, exercice: int) -> PreClotureResultat:
    return calculer_precloture_snapshot(charger_snapshot(db, cabinet_id=cabinet_id, entreprise_id=entreprise_id, exercice=exercice))
