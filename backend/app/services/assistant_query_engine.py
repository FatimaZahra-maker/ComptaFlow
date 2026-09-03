"""Moteur de lecture contrôlé : QueryPlan validé -> SQLAlchemy/services métier."""

from __future__ import annotations

import uuid
import calendar
from difflib import SequenceMatcher
from dataclasses import asdict, is_dataclass
from datetime import date
from decimal import Decimal
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.models.audit_log import AuditLog
from app.models.compte_bancaire_entreprise import CompteBancaireEntreprise
from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import CategorieDocumentEnum, RoleEnum, StatutValidationEnum, TypeEcritureEnum
from app.models.ligne_comptable import LigneComptable
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.models.regularisation_cloture import RegularisationCloture
from app.models.tache import Tache
from app.models.user import User
from app.schemas.assistant import (
    AssistantAction, AssistantCompanyCard, AssistantDataCard, AssistantDocumentCard,
    AssistantResponse, AssistantSource,
)
from app.schemas.assistant_query_plan import AssistantDomain, DateField, PaymentStatus, QueryOperation, QueryPlan
from app.services import (
    alertes_service, bilan_service, cpc_service, ligne_comptable_service, precloture_service,
    tva_comptable_service,
)
from app.services.assistant_semantic_registry import normalize_text, validate_plan


ADMIN_ROLES = {RoleEnum.ADMIN_CABINET, RoleEnum.SUPER_ADMIN}
SAFE_EXTRACTED_FIELDS = {
    "numero_piece", "date_piece", "nom_fournisseur", "nom_client", "tiers",
    "ice_fournisseur", "ice_client", "if_fournisseur", "if_client",
    "rc_fournisseur", "rc_client", "adresse", "devise", "devise_originale",
    "montant_ht", "montant_tva", "montant_ttc", "taux_tva", "nature_comptable",
    "categorie", "categorie_document", "source_extraction", "a_verifier",
    "raison_verification", "confiance_par_champ",
}


class QueryEngineForbidden(Exception):
    pass


class QueryEngineNotFound(Exception):
    pass


def _value(value: Any) -> Any:
    if hasattr(value, "value"):
        return value.value
    if is_dataclass(value):
        return asdict(value)
    return value


def _company_scope(user: User):
    return select(Entreprise).where(
        Entreprise.cabinet_id == user.cabinet_id,
        Entreprise.is_active.is_(True),
        Entreprise.creee_automatiquement.is_(False),
    )


def _resolve_company(db: Session, user: User, plan: QueryPlan) -> Entreprise | None:
    requested_id = plan.filters.entreprise_id
    query = _company_scope(user)
    if requested_id:
        company = db.execute(query.where(Entreprise.id == requested_id)).scalar_one_or_none()
        if company is None:
            raise QueryEngineNotFound("Entreprise introuvable dans les données autorisées.")
        return company
    if plan.filters.entreprise:
        name = plan.filters.entreprise.strip()
        companies = db.execute(query.where(Entreprise.nom.ilike(f"%{name}%"))).scalars().all()
        if not companies:
            scoped = db.execute(query).scalars().all()
            companies = [item for item in scoped if SequenceMatcher(None, normalize_text(name), normalize_text(item.nom)).ratio() >= 0.78]
        if len(companies) > 1:
            raise QueryEngineNotFound("Plusieurs entreprises correspondent. Précisez le nom complet.")
        if not companies:
            raise QueryEngineNotFound("Entreprise introuvable dans les données autorisées.")
        return companies[0]
    if plan.filters.texte:
        companies = db.execute(query.where(Entreprise.nom.ilike(f"%{plan.filters.texte}%"))).scalars().all()
        if len(companies) == 1:
            return companies[0]
    return None


def _company_card(company: Entreprise) -> AssistantCompanyCard:
    return AssistantCompanyCard(
        entreprise_id=company.id, nom=company.nom, ice=company.ice,
        identifiant_fiscal=None, is_active=bool(company.is_active),
        actions=[AssistantAction(label="Voir les documents", kind="route", route=f"/chronos?entreprise_id={company.id}")],
    )


def _document_card(document: Document, entry: EcritureComptable | None,
                   company: Entreprise | None, *, extracted: bool = False,
                   paid_amount: Decimal = Decimal("0")) -> AssistantDocumentCard:
    raw = document.donnees_extraites if isinstance(document.donnees_extraites, dict) else {}
    safe = {key: raw.get(key) for key in SAFE_EXTRACTED_FIELDS if key in raw}
    anomalies = []
    if entry and entry.anomalie_detectee and entry.anomalie_details:
        anomalies.append(entry.anomalie_details)
    if safe.get("raison_verification"):
        anomalies.append(str(safe["raison_verification"]))
    remaining = max(Decimal("0"), Decimal(entry.montant_ttc) - paid_amount) if entry else None
    payment_status = None if not entry else "paye" if remaining == 0 else "partiel" if paid_amount > 0 else "impaye"
    actions = [
        AssistantAction(label="Voir la fiche document", kind="route", route=f"/documents/{document.id}"),
        AssistantAction(label="Ouvrir la pièce originale", kind="secure_file", api_path=f"/documents/{document.id}/fichier", filename=document.nom_fichier_original),
    ]
    if entry:
        actions.append(AssistantAction(label="Voir la pré-écriture", kind="route", route="/registers"))
    if paid_amount > 0:
        actions.append(AssistantAction(label="Voir les paiements", kind="route", route="/banque"))
    return AssistantDocumentCard(
        document_id=document.id, entreprise_id=document.entreprise_id,
        entreprise=company.nom if company else None,
        categorie=_value(document.categorie), tiers=entry.tiers if entry else safe.get("tiers"),
        numero_facture=entry.numero_piece if entry else safe.get("numero_piece"),
        date_facture=entry.date_piece if entry else None, date_importation=document.created_at,
        montant_ht=entry.montant_ht if entry else safe.get("montant_ht"),
        montant_tva=entry.montant_tva if entry else safe.get("montant_tva"),
        montant_ttc=entry.montant_ttc if entry else safe.get("montant_ttc"),
        devise=str(safe.get("devise_originale") or safe.get("devise") or (entry.devise_originale if entry else "MAD")),
        statut_document=str(_value(document.statut)),
        statut_ecriture=str(_value(entry.statut_validation)) if entry else None,
        statut_paiement=payment_status, montant_regle=paid_amount if entry else None,
        restant_du=remaining,
        saisie_topaze=bool(document.saisie_topaze), anomalies=anomalies,
        donnees_extraites=safe if extracted else None,
        actions=actions,
    )


def _response(plan: QueryPlan, conversation_id: uuid.UUID, *, response_type: str,
              message: str, **kwargs) -> AssistantResponse:
    public_filters = plan.filters.model_dump(mode="json", exclude_none=True, exclude_defaults=True)
    for internal in ("entreprise_id", "resource_id", "resource_ids"):
        public_filters.pop(internal, None)
    return AssistantResponse(
        conversation_id=conversation_id, response_type=response_type, intent=plan.domain.value,
        message=message, filters=public_filters,
        plan_summary={"domain": plan.domain.value, "operation": plan.operation.value, "entity": plan.entity.value},
        page=plan.page, page_size=plan.limit, **kwargs,
    )


def _period(plan: QueryPlan) -> tuple[date | None, date | None]:
    if plan.filters.date_debut or plan.filters.date_fin:
        return plan.filters.date_debut, plan.filters.date_fin
    if plan.filters.annee and plan.filters.mois:
        start = date(plan.filters.annee, plan.filters.mois, 1)
        end = date(plan.filters.annee, plan.filters.mois, calendar.monthrange(plan.filters.annee, plan.filters.mois)[1])
        return start, end
    if plan.filters.annee:
        return date(plan.filters.annee, 1, 1), date(plan.filters.annee, 12, 31)
    return None, None


def _execute_companies(db: Session, user: User, plan: QueryPlan, conversation_id: uuid.UUID) -> AssistantResponse:
    query = _company_scope(user)
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    rows = db.execute(query.order_by(Entreprise.nom).offset((plan.page - 1) * plan.limit).limit(plan.limit + 1)).scalars().all()
    has_more = len(rows) > plan.limit
    rows = rows[:plan.limit]
    if plan.operation == QueryOperation.COUNT:
        return _response(plan, conversation_id, response_type="aggregate", message=f"{total} entreprise(s) accessible(s).", total_count=total, aggregate={"count": total}, companies=[_company_card(row) for row in rows], has_more=has_more)
    return _response(plan, conversation_id, response_type="company_list" if rows else "no_result", message=f"Vous avez accès à {total} entreprise(s)." if rows else "Aucune entreprise n'est actuellement disponible pour votre compte.", companies=[_company_card(row) for row in rows], total_count=total, has_more=has_more)


def _document_query(user: User, plan: QueryPlan, company: Entreprise | None):
    query = (
        select(Document, EcritureComptable, Entreprise)
        .outerjoin(EcritureComptable, EcritureComptable.document_id == Document.id)
        .outerjoin(Entreprise, Entreprise.id == Document.entreprise_id)
        .where(Document.cabinet_id == user.cabinet_id)
    )
    if company:
        query = query.where(Document.entreprise_id == company.id)
    if plan.filters.resource_id:
        query = query.where(Document.id == plan.filters.resource_id)
    if plan.filters.resource_ids:
        query = query.where(Document.id.in_(plan.filters.resource_ids))
    if plan.domain == AssistantDomain.FACTURES_ACHAT:
        query = query.where(EcritureComptable.type_ecriture == TypeEcritureEnum.ACHAT)
    elif plan.domain == AssistantDomain.FACTURES_VENTE:
        query = query.where(EcritureComptable.type_ecriture == TypeEcritureEnum.VENTE)
    elif plan.domain == AssistantDomain.FOURNISSEURS:
        query = query.where(EcritureComptable.type_ecriture == TypeEcritureEnum.ACHAT)
    elif plan.domain == AssistantDomain.CLIENTS:
        query = query.where(EcritureComptable.type_ecriture == TypeEcritureEnum.VENTE)
    elif plan.domain == AssistantDomain.RELEVES_BANCAIRES:
        query = query.where(Document.categorie == CategorieDocumentEnum.BANQUE)
    if plan.filters.numero_facture:
        query = query.where(EcritureComptable.numero_piece.ilike(f"%{plan.filters.numero_facture}%"))
    tiers = plan.filters.fournisseur or plan.filters.client or plan.filters.tiers
    if tiers:
        query = query.where(EcritureComptable.tiers.ilike(f"%{tiers}%"))
    if plan.filters.texte and company is None:
        query = query.where(or_(
            EcritureComptable.tiers.ilike(f"%{plan.filters.texte}%"),
            EcritureComptable.numero_piece.ilike(f"%{plan.filters.texte}%"),
            Document.nom_fichier_original.ilike(f"%{plan.filters.texte}%"),
            Document.texte_ocr.ilike(f"%{plan.filters.texte}%"),
        ))
    if plan.filters.montant_exact is not None:
        query = query.where(EcritureComptable.montant_ttc == plan.filters.montant_exact)
    if plan.filters.montant_min is not None:
        query = query.where(EcritureComptable.montant_ttc >= plan.filters.montant_min)
    if plan.filters.montant_max is not None:
        query = query.where(EcritureComptable.montant_ttc <= plan.filters.montant_max)
    date_column = func.date(Document.created_at) if plan.filters.date_type == DateField.IMPORTATION else EcritureComptable.date_piece
    if plan.filters.date_exacte:
        query = query.where(date_column == plan.filters.date_exacte)
    start, end = _period(plan)
    if start:
        query = query.where(date_column >= start)
    if end:
        query = query.where(date_column <= end)
    if plan.filters.statut_topaze is not None:
        query = query.where(Document.saisie_topaze.is_(plan.filters.statut_topaze))
    if plan.domain == AssistantDomain.A_VERIFIER or plan.filters.statut == "a_verifier":
        query = query.where(or_(EcritureComptable.statut_validation == StatutValidationEnum.A_VERIFIER, EcritureComptable.anomalie_detectee.is_(True)))
    return query


def _execute_documents(db: Session, user: User, plan: QueryPlan, conversation_id: uuid.UUID,
                       company: Entreprise | None) -> AssistantResponse:
    query = _document_query(user, plan, company)
    # Le statut de paiement est calculé sur les allocations confirmées, sans changer la source comptable.
    if plan.filters.statut_paiement:
        allocated = (
            select(RapprochementBancaireAllocation.ecriture_id, func.coalesce(func.sum(RapprochementBancaireAllocation.montant_affecte), 0).label("paid"))
            .where(RapprochementBancaireAllocation.cabinet_id == user.cabinet_id, RapprochementBancaireAllocation.statut == "confirme")
            .group_by(RapprochementBancaireAllocation.ecriture_id).subquery()
        )
        query = query.outerjoin(allocated, allocated.c.ecriture_id == EcritureComptable.id)
        paid = func.coalesce(allocated.c.paid, 0)
        if plan.filters.statut_paiement == PaymentStatus.PAYE:
            query = query.where(paid >= EcritureComptable.montant_ttc)
        elif plan.filters.statut_paiement == PaymentStatus.PARTIEL:
            query = query.where(paid > 0, paid < EcritureComptable.montant_ttc)
        else:
            query = query.where(paid == 0)
    count_query = select(func.count()).select_from(query.subquery())
    total = db.execute(count_query).scalar_one()
    if plan.operation == QueryOperation.COUNT:
        return _response(plan, conversation_id, response_type="aggregate", message=f"{total} résultat(s).", total_count=total, aggregate={"count": total})
    if plan.operation == QueryOperation.SUM:
        subquery = query.subquery()
        amount = db.execute(select(func.coalesce(func.sum(subquery.c.montant_ttc), 0))).scalar_one()
        return _response(plan, conversation_id, response_type="aggregate", message=f"Montant total : {amount} MAD.", total_count=total, aggregate={"type_donnees": "pré-écritures correspondant aux filtres", "nombre_elements": total, "montant_ttc": amount, "devise": "MAD"})
    if plan.operation in {QueryOperation.GROUP, QueryOperation.COMPARE}:
        subquery = query.subquery()
        group_name = plan.group_by or "mois"
        if group_name in {"tiers", "fournisseur", "client"}:
            group_expr = subquery.c.tiers
        elif group_name == "entreprise":
            group_expr = subquery.c.entreprise_id
        elif group_name == "categorie":
            group_expr = subquery.c.categorie
        else:
            group_expr = func.extract("month", subquery.c.date_piece)
        grouped_query = select(
            group_expr.label("groupe"), func.count().label("nombre"),
            func.coalesce(func.sum(subquery.c.montant_ttc), 0).label("montant_ttc"),
        ).where(group_expr.is_not(None)).group_by(group_expr).order_by(group_expr)
        if plan.filters.mois_comparaison and group_name == "mois":
            grouped_query = grouped_query.where(group_expr.in_(plan.filters.mois_comparaison))
        groups = [
            {"groupe": str(row.groupe), "nombre": row.nombre, "montant_ttc": row.montant_ttc}
            for row in db.execute(grouped_query).all()
        ]
        return _response(plan, conversation_id, response_type="aggregate", message=f"Comparaison de {len(groups)} groupe(s).", total_count=total, aggregate={"group_by": group_name, "groupes": groups, "devise": "MAD"})
    page_limit = 1 if plan.operation in {QueryOperation.FIND_ONE, QueryOperation.OPEN} else plan.limit
    if plan.sort and plan.sort.field == "montant":
        order_column = EcritureComptable.montant_ttc
    elif plan.sort and plan.sort.field == "date":
        order_column = EcritureComptable.date_piece
    else:
        order_column = Document.created_at
    order_expression = order_column.asc() if plan.sort and plan.sort.direction.value == "asc" else order_column.desc()
    rows = db.execute(query.order_by(order_expression).offset((plan.page - 1) * page_limit).limit(page_limit + 1)).all()
    has_more = len(rows) > page_limit
    rows = rows[:page_limit]
    entry_ids = [row[1].id for row in rows if row[1]]
    paid_by_entry: dict[uuid.UUID, Decimal] = {}
    if entry_ids:
        allocations = db.execute(
            select(RapprochementBancaireAllocation.ecriture_id, func.sum(RapprochementBancaireAllocation.montant_affecte))
            .where(
                RapprochementBancaireAllocation.cabinet_id == user.cabinet_id,
                RapprochementBancaireAllocation.ecriture_id.in_(entry_ids),
                RapprochementBancaireAllocation.statut == "confirme",
            ).group_by(RapprochementBancaireAllocation.ecriture_id)
        ).all()
        paid_by_entry = {entry_id: Decimal(amount or 0) for entry_id, amount in allocations}
    cards = [_document_card(row[0], row[1], row[2], extracted=plan.domain == AssistantDomain.DONNEES_EXTRAITES, paid_amount=paid_by_entry.get(row[1].id, Decimal("0")) if row[1] else Decimal("0")) for row in rows]
    sources = [AssistantSource(resource_type="document", resource_id=card.document_id, label=card.numero_facture or "Document", route=f"/documents/{card.document_id}") for card in cards]
    response_type = "single_document" if len(cards) == 1 and plan.operation in {QueryOperation.FIND_ONE, QueryOperation.OPEN} else "document_list" if cards else "no_result"
    return _response(plan, conversation_id, response_type=response_type, message=f"{total} résultat(s) trouvé(s)." if cards else "Aucun résultat dans votre périmètre.", documents=cards, sources=sources, total_count=total, has_more=has_more, context_document_id=cards[0].document_id if len(cards) == 1 else None)


def _execute_tiers(db: Session, user: User, plan: QueryPlan, conversation_id: uuid.UUID,
                   company: Entreprise | None) -> AssistantResponse:
    entry_type = TypeEcritureEnum.ACHAT if plan.domain == AssistantDomain.FOURNISSEURS else TypeEcritureEnum.VENTE
    query = select(
        EcritureComptable.tiers.label("tiers"),
        func.count(EcritureComptable.id).label("nombre_factures"),
        func.coalesce(func.sum(EcritureComptable.montant_ttc), 0).label("montant_ttc"),
    ).where(
        EcritureComptable.cabinet_id == user.cabinet_id,
        EcritureComptable.type_ecriture == entry_type,
        EcritureComptable.tiers.is_not(None),
    )
    if company:
        query = query.where(EcritureComptable.entreprise_id == company.id)
    tiers_filter = plan.filters.fournisseur or plan.filters.client or plan.filters.tiers
    if tiers_filter:
        query = query.where(EcritureComptable.tiers.ilike(f"%{tiers_filter}%"))
    start, end = _period(plan)
    if start:
        query = query.where(EcritureComptable.date_piece >= start)
    if end:
        query = query.where(EcritureComptable.date_piece <= end)
    grouped = query.group_by(EcritureComptable.tiers)
    total = db.execute(select(func.count()).select_from(grouped.subquery())).scalar_one()
    if plan.operation == QueryOperation.COUNT:
        return _response(plan, conversation_id, response_type="aggregate", message=f"{total} tiers distinct(s).", total_count=total, aggregate={"count": total})
    rows = db.execute(grouped.order_by(EcritureComptable.tiers).offset((plan.page - 1) * plan.limit).limit(plan.limit + 1)).all()
    has_more = len(rows) > plan.limit
    items = [{"nom": row.tiers, "nombre_factures": row.nombre_factures, "montant_ttc": row.montant_ttc} for row in rows[:plan.limit]]
    return _response(plan, conversation_id, response_type="aggregate" if items else "no_result", message=f"{total} tiers distinct(s)." if items else "Aucun tiers correspondant.", total_count=total, aggregate={"type": plan.domain.value, "tiers": items} if items else None, has_more=has_more)


def _generic_card(resource_type: str, row: Any, title: str, fields: dict[str, Any], route: str | None = None) -> AssistantDataCard:
    actions = [AssistantAction(label="Ouvrir", kind="route", route=route)] if route else []
    return AssistantDataCard(resource_type=resource_type, resource_id=row.id, title=title, fields={key: _value(value) for key, value in fields.items()}, actions=actions)


def _execute_rows(db: Session, user: User, plan: QueryPlan, conversation_id: uuid.UUID,
                  company: Entreprise | None) -> AssistantResponse:
    model: Any
    route = None
    if plan.domain in {AssistantDomain.ECRITURES, AssistantDomain.TOPAZE, AssistantDomain.A_VERIFIER}:
        model = EcritureComptable
        query = select(model).where(model.cabinet_id == user.cabinet_id)
        if plan.domain == AssistantDomain.TOPAZE:
            query = query.where(model.saisie_topaze.is_(plan.filters.statut_topaze if plan.filters.statut_topaze is not None else False))
        if plan.domain == AssistantDomain.A_VERIFIER:
            query = query.where(or_(model.statut_validation == StatutValidationEnum.A_VERIFIER, model.anomalie_detectee.is_(True)))
        route = "/ecritures"
        title = lambda row: row.numero_piece or "Pré-écriture"
        fields = lambda row: {"date": row.date_piece, "tiers": row.tiers, "montant_ttc": row.montant_ttc, "statut": row.statut_validation, "topaze": row.saisie_topaze}
    elif plan.domain == AssistantDomain.LIGNES_ECRITURE:
        model = LigneComptable
        query = select(model).where(model.cabinet_id == user.cabinet_id, model.est_validee.is_(True))
        if plan.filters.compte_prefixe:
            query = query.where(model.compte.startswith(plan.filters.compte_prefixe))
        title = lambda row: f"Compte {row.compte}"
        fields = lambda row: {"date": row.date_ecriture, "journal": row.journal, "débit": row.debit, "crédit": row.credit, "libellé": row.libelle}
    elif plan.domain in {AssistantDomain.MOUVEMENTS_BANCAIRES, AssistantDomain.RAPPROCHEMENTS}:
        model = MouvementBancaire
        query = select(model).where(model.cabinet_id == user.cabinet_id)
        if plan.domain == AssistantDomain.RAPPROCHEMENTS and plan.filters.statut:
            query = query.where(model.statut_rapprochement == plan.filters.statut)
        title = lambda row: row.libelle
        fields = lambda row: {"date": row.date_operation, "montant": row.montant, "référence": row.reference, "statut": row.statut_rapprochement, "mode": row.mode_rapprochement}
        route = "/banque"
    elif plan.domain in {AssistantDomain.ALLOCATIONS, AssistantDomain.PAIEMENTS}:
        model = RapprochementBancaireAllocation
        query = select(model).where(model.cabinet_id == user.cabinet_id)
        if plan.filters.resource_id:
            query = query.join(EcritureComptable, EcritureComptable.id == model.ecriture_id).where(
                EcritureComptable.cabinet_id == user.cabinet_id,
                EcritureComptable.document_id == plan.filters.resource_id,
            )
        title = lambda row: "Affectation bancaire"
        fields = lambda row: {"montant_affecté": row.montant_affecte, "statut": row.statut, "score": row.score, "écriture_id": row.ecriture_id, "mouvement_id": row.mouvement_bancaire_id}
        route = "/banque"
    elif plan.domain == AssistantDomain.TACHES:
        model = Tache
        query = select(model).where(model.cabinet_id == user.cabinet_id)
        if plan.filters.statut == "en_retard":
            query = query.where(model.date_echeance < date.today(), model.statut != "terminee")
        elif plan.filters.statut:
            query = query.where(model.statut == plan.filters.statut)
        title = lambda row: row.titre
        fields = lambda row: {"échéance": row.date_echeance, "statut": row.statut, "priorité": row.priorite}
        route = "/taches"
    elif plan.domain == AssistantDomain.COMPTES_BANCAIRES:
        model = CompteBancaireEntreprise
        query = select(model).where(model.cabinet_id == user.cabinet_id)
        title = lambda row: row.libelle
        fields = lambda row: {"banque": row.banque_nom, "IBAN": row.iban, "devise": row.devise, "compte_comptable": row.numero_compte_comptable, "actif": row.is_active}
    elif plan.domain == AssistantDomain.PLAN_COMPTABLE:
        model = CompteComptableEntreprise
        query = select(model).where(model.cabinet_id == user.cabinet_id)
        if plan.filters.compte_prefixe:
            query = query.where(model.numero_compte.startswith(plan.filters.compte_prefixe))
        title = lambda row: f"{row.numero_compte} — {row.libelle}"
        fields = lambda row: {"usage": row.type_usage, "famille": row.famille_cgnc, "actif": row.is_active}
    elif plan.domain == AssistantDomain.AUDIT:
        if user.role not in ADMIN_ROLES:
            raise QueryEngineForbidden("Le journal d'audit est réservé aux administrateurs autorisés.")
        model = AuditLog
        query = select(model).where(model.cabinet_id == user.cabinet_id)
        if plan.filters.resource_id:
            query = query.where(model.resource_type == "document", model.resource_id == plan.filters.resource_id)
        elif plan.filters.numero_facture:
            document_ids = select(EcritureComptable.document_id).where(
                EcritureComptable.cabinet_id == user.cabinet_id,
                EcritureComptable.numero_piece.ilike(f"%{plan.filters.numero_facture}%"),
            )
            query = query.where(model.resource_type == "document", model.resource_id.in_(document_ids))
        title = lambda row: str(_value(row.action))
        fields = lambda row: {"date": row.created_at, "statut": row.status, "ressource": row.resource_type, "description": row.description}
        route = "/historique"
    elif plan.domain == AssistantDomain.CLOTURE:
        model = RegularisationCloture
        query = select(model).where(model.cabinet_id == user.cabinet_id)
        if plan.filters.statut:
            query = query.where(model.statut == plan.filters.statut)
        title = lambda row: row.libelle
        fields = lambda row: {"exercice": row.exercice, "type": row.type_regularisation, "montant": row.montant, "statut": row.statut, "anomalies": row.anomalies}
        route = "/cloture"
    else:
        return _response(plan, conversation_id, response_type="clarification", message="Cette lecture nécessite une précision supplémentaire.", clarification_question="Quel dossier et quelle période souhaitez-vous consulter ?")
    if company and hasattr(model, "entreprise_id"):
        query = query.where(model.entreprise_id == company.id)
    start, end = _period(plan)
    date_field = None
    for candidate in ("date_piece", "date_operation", "date_echeance", "date_ecriture"):
        if hasattr(model, candidate):
            date_field = getattr(model, candidate)
            break
    if start and date_field is not None:
        query = query.where(date_field >= start)
    if end and date_field is not None:
        query = query.where(date_field <= end)
    total = db.execute(select(func.count()).select_from(query.subquery())).scalar_one()
    if plan.operation == QueryOperation.COUNT:
        return _response(plan, conversation_id, response_type="aggregate", message=f"{total} résultat(s).", aggregate={"count": total}, total_count=total)
    if plan.operation == QueryOperation.SUM:
        aggregate: dict[str, Any] = {"count": total}
        if model is EcritureComptable:
            subquery = query.subquery()
            aggregate["montant_ttc"] = db.execute(select(func.coalesce(func.sum(subquery.c.montant_ttc), 0))).scalar_one()
        elif model is MouvementBancaire:
            subquery = query.subquery()
            aggregate["montant"] = db.execute(select(func.coalesce(func.sum(subquery.c.montant), 0))).scalar_one()
        elif model is RapprochementBancaireAllocation:
            subquery = query.subquery()
            aggregate["montant_affecte"] = db.execute(select(func.coalesce(func.sum(subquery.c.montant_affecte), 0))).scalar_one()
        elif model is LigneComptable:
            subquery = query.subquery()
            aggregate["total_debit"] = db.execute(select(func.coalesce(func.sum(subquery.c.debit), 0))).scalar_one()
            aggregate["total_credit"] = db.execute(select(func.coalesce(func.sum(subquery.c.credit), 0))).scalar_one()
        return _response(plan, conversation_id, response_type="aggregate", message="Agrégat calculé sur les données autorisées.", aggregate=aggregate, total_count=total)
    rows = db.execute(query.order_by(model.created_at.desc()).offset((plan.page - 1) * plan.limit).limit(plan.limit + 1)).scalars().all()
    has_more = len(rows) > plan.limit
    rows = rows[:plan.limit]
    cards = [_generic_card(plan.domain.value, row, title(row), fields(row), route) for row in rows]
    return _response(plan, conversation_id, response_type="data_list" if cards else "no_result", message=f"{total} résultat(s) trouvé(s)." if cards else "Aucun résultat dans votre périmètre.", data=cards, total_count=total, has_more=has_more, sources=[AssistantSource(resource_type=plan.domain.value, resource_id=row.id, label=title(row), route=route) for row in rows])


def _execute_statement(db: Session, user: User, plan: QueryPlan, conversation_id: uuid.UUID,
                       company: Entreprise | None) -> AssistantResponse:
    if company is None:
        return _response(plan, conversation_id, response_type="clarification", message="Le dossier comptable est nécessaire pour cet état.", clarification_question="Pour quelle entreprise souhaitez-vous cet état ?")
    year = plan.filters.annee or date.today().year
    start, end = _period(plan)
    if plan.domain == AssistantDomain.TVA:
        result = tva_comptable_service.calculer_tva_annuelle(db, cabinet_id=user.cabinet_id, entreprise_id=company.id, annee=year)
        aggregate = {key: _value(value) for key, value in asdict(result).items() if key.startswith("total_") or key in {"annee", "nombre_mois_a_verifier"}}
        aggregate.update({
            "entreprise": company.nom,
            "type_donnees": "lignes comptables et écritures validées",
            "nombre_ecritures": sum(month.nombre_ecritures for month in result.mensualites),
            "elements_a_verifier": result.nombre_mois_a_verifier,
        })
        if plan.operation == QueryOperation.COMPARE or plan.filters.mois:
            selected = set(plan.filters.mois_comparaison or ([plan.filters.mois] if plan.filters.mois else range(1, 13)))
            aggregate["mensualites"] = [
                {key: _value(value) for key, value in asdict(month).items() if key not in {"comptes", "raisons_verification"}}
                for month in result.mensualites if month.mois in selected
            ]
    elif plan.domain == AssistantDomain.GRAND_LIVRE:
        result = ligne_comptable_service.obtenir_grand_livre(db, cabinet_id=user.cabinet_id, entreprise_id=company.id, date_debut=start, date_fin=end, compte_prefix=plan.filters.compte_prefixe)
        aggregate = {key: value for key, value in result.items() if key not in {"comptes"}}
    elif plan.domain == AssistantDomain.BALANCE:
        result = ligne_comptable_service.obtenir_balance(db, cabinet_id=user.cabinet_id, entreprise_id=company.id, date_debut=start, date_fin=end)
        aggregate = {key: value for key, value in result.items() if key != "lignes"}
    elif plan.domain == AssistantDomain.CPC:
        result = cpc_service.calculer_cpc(db, cabinet_id=user.cabinet_id, entreprise_id=company.id, annee=year)
        aggregate = {key: _value(value) for key, value in asdict(result).items() if not isinstance(value, (list, dict))}
    elif plan.domain == AssistantDomain.BILAN:
        result = bilan_service.calculer_bilan(db, cabinet_id=user.cabinet_id, entreprise_id=company.id, annee=year)
        aggregate = {key: _value(value) for key, value in asdict(result).items() if not isinstance(value, (list, dict))}
    elif plan.domain == AssistantDomain.PRE_CLOTURE:
        result = precloture_service.calculer_precloture(db, cabinet_id=user.cabinet_id, entreprise_id=company.id, exercice=year)
        raw = asdict(result)
        aggregate = {key: _value(value) for key, value in raw.items() if not isinstance(value, (list, dict))}
    else:
        return _response(plan, conversation_id, response_type="clarification", message="Cette synthèse n'est pas encore disponible en lecture conversationnelle.", clarification_question="Souhaitez-vous consulter le Grand Livre, la Balance, la TVA, le CPC, le Bilan ou la pré-clôture ?")
    return _response(plan, conversation_id, response_type="aggregate", message=f"Synthèse {plan.domain.value} de {company.nom} pour {year}.", aggregate=aggregate, sources=[AssistantSource(resource_type="entreprise", resource_id=company.id, label=company.nom, route=f"/chronos?entreprise_id={company.id}")])


def _execute_alerts(db: Session, user: User, plan: QueryPlan,
                    conversation_id: uuid.UUID) -> AssistantResponse:
    entries = alertes_service.lister_ecritures_non_saisies(db, user.cabinet_id)
    delays = alertes_service.lister_entreprises_en_retard(db, user.cabinet_id)
    total = len(entries) + len(delays)
    if plan.operation == QueryOperation.COUNT:
        return _response(plan, conversation_id, response_type="aggregate", message=f"{total} alerte(s) active(s).", total_count=total, aggregate={"écritures_non_saisies": len(entries), "entreprises_en_retard": len(delays)})
    cards = [AssistantDataCard(resource_type="alerte_topaze", resource_id=item.id, title=item.numero_piece or "Pré-écriture non saisie", subtitle=item.entreprise_nom, fields={"date": item.date_piece, "tiers": item.tiers, "montant_ttc": item.montant_ttc}, actions=[AssistantAction(label="Voir les alertes", kind="route", route="/rappels")]) for item in entries[:plan.limit]]
    remaining = max(0, plan.limit - len(cards))
    cards.extend(AssistantDataCard(resource_type="alerte_retard", resource_id=item.entreprise_id, title=item.entreprise_nom, fields={"dernier_upload": item.dernier_upload, "jours_de_retard": item.jours_de_retard}, actions=[AssistantAction(label="Voir les documents", kind="route", route=f"/chronos?entreprise_id={item.entreprise_id}")]) for item in delays[:remaining])
    return _response(plan, conversation_id, response_type="data_list" if cards else "no_result", message=f"{total} alerte(s) active(s)." if cards else "Aucune alerte active.", data=cards, total_count=total, has_more=total > len(cards))


DOCUMENT_DOMAINS = {
    AssistantDomain.DOCUMENTS, AssistantDomain.FACTURES_ACHAT,
    AssistantDomain.FACTURES_VENTE, AssistantDomain.RELEVES_BANCAIRES,
    AssistantDomain.DONNEES_EXTRAITES, AssistantDomain.CHRONOS,
    AssistantDomain.FOURNISSEURS, AssistantDomain.CLIENTS,
}
ROW_DOMAINS = {
    AssistantDomain.ECRITURES, AssistantDomain.LIGNES_ECRITURE,
    AssistantDomain.MOUVEMENTS_BANCAIRES, AssistantDomain.RAPPROCHEMENTS,
    AssistantDomain.ALLOCATIONS, AssistantDomain.PAIEMENTS,
    AssistantDomain.COMPTES_BANCAIRES, AssistantDomain.PLAN_COMPTABLE,
    AssistantDomain.TACHES, AssistantDomain.A_VERIFIER, AssistantDomain.TOPAZE,
    AssistantDomain.AUDIT,
    AssistantDomain.CLOTURE,
}
STATEMENT_DOMAINS = {
    AssistantDomain.TVA, AssistantDomain.GRAND_LIVRE, AssistantDomain.BALANCE,
    AssistantDomain.CPC, AssistantDomain.BILAN, AssistantDomain.PRE_CLOTURE,
}


def execute(db: Session, user: User, plan: QueryPlan, conversation_id: uuid.UUID) -> AssistantResponse:
    validate_plan(plan)
    if plan.domain == AssistantDomain.UNKNOWN:
        return _response(plan, conversation_id, response_type="clarification", message="Je n'ai pas identifié une lecture comptable précise.", clarification_question="Cherchez-vous une facture, un paiement, une tâche, une entreprise ou un état comptable ?")
    if plan.domain == AssistantDomain.ALERTES:
        return _execute_alerts(db, user, plan, conversation_id)
    company = _resolve_company(db, user, plan)
    if plan.domain == AssistantDomain.ENTREPRISES:
        return _execute_companies(db, user, plan, conversation_id)
    if plan.domain in {AssistantDomain.FOURNISSEURS, AssistantDomain.CLIENTS}:
        return _execute_tiers(db, user, plan, conversation_id, company)
    if plan.domain in DOCUMENT_DOMAINS:
        return _execute_documents(db, user, plan, conversation_id, company)
    if plan.domain == AssistantDomain.PAIEMENTS and plan.filters.statut_paiement:
        return _execute_documents(db, user, plan, conversation_id, company)
    if plan.domain in ROW_DOMAINS:
        return _execute_rows(db, user, plan, conversation_id, company)
    if plan.domain in STATEMENT_DOMAINS:
        return _execute_statement(db, user, plan, conversation_id, company)
    return _response(plan, conversation_id, response_type="clarification", message="Cette lecture nécessite une précision.", clarification_question="Pouvez-vous préciser le dossier et la période ?")
