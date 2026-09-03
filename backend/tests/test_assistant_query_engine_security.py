from datetime import date, datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import (
    CategorieDocumentEnum,
    RoleEnum,
    StatutDocumentEnum,
    StatutValidationEnum,
    TypeEcritureEnum,
)
from app.schemas.assistant_query_plan import (
    AssistantDomain,
    QueryEntity,
    QueryFilters,
    QueryOperation,
    QueryPlan,
)
from app.services import assistant_query_engine


def _user(role: RoleEnum = RoleEnum.COLLABORATEUR):
    return SimpleNamespace(id=uuid.uuid4(), cabinet_id=uuid.uuid4(), role=role)


def _document_objects(user):
    company = Entreprise(cabinet_id=user.cabinet_id, nom="ANZOBAT", is_active=True)
    company.id = uuid.uuid4()
    document = Document(
        cabinet_id=user.cabinet_id,
        entreprise_id=company.id,
        uploaded_by=user.id,
        nom_fichier_original="FA-2026-120.pdf",
        chemin_stockage="storage_local/secret/document.pdf",
        hash_fichier="a" * 64,
        statut=StatutDocumentEnum.VALIDE,
        categorie=CategorieDocumentEnum.ACHATS,
        saisie_topaze=False,
        donnees_extraites={"numero_piece": "FA-2026-120", "montant_ttc": "12000"},
    )
    document.id = uuid.uuid4()
    document.created_at = datetime(2026, 8, 12, 9, 0, tzinfo=timezone.utc)
    entry = EcritureComptable(
        cabinet_id=user.cabinet_id,
        entreprise_id=company.id,
        document_id=document.id,
        type_ecriture=TypeEcritureEnum.ACHAT,
        numero_piece="FA-2026-120",
        date_piece=date(2026, 8, 12),
        tiers="ALMAZ",
        montant_ht=Decimal("10000"),
        montant_tva=Decimal("2000"),
        montant_ttc=Decimal("12000"),
        statut_validation=StatutValidationEnum.VALIDE,
    )
    entry.id = uuid.uuid4()
    return company, document, entry


def test_requete_document_applique_cabinet_et_entreprise():
    user = _user()
    company_id = uuid.uuid4()
    company = SimpleNamespace(id=company_id)
    plan = QueryPlan(
        domain=AssistantDomain.DOCUMENTS,
        operation=QueryOperation.LIST,
        entity=QueryEntity.DOCUMENT,
        filters=QueryFilters(entreprise_id=company_id),
    )

    sql = str(assistant_query_engine._document_query(user, plan, company))

    assert "documents.cabinet_id" in sql
    assert "documents.entreprise_id" in sql


def test_requete_documents_bancaires_filtre_la_categorie_banque():
    user = _user()
    plan = QueryPlan(
        domain=AssistantDomain.RELEVES_BANCAIRES,
        operation=QueryOperation.LIST,
        entity=QueryEntity.DOCUMENT,
    )

    sql = str(assistant_query_engine._document_query(user, plan, None))

    assert "documents.cabinet_id" in sql
    assert "documents.categorie" in sql


def test_carte_document_utilise_un_lien_securise_et_calcule_le_restant_du():
    user = _user()
    company, document, entry = _document_objects(user)

    card = assistant_query_engine._document_card(
        document,
        entry,
        company,
        paid_amount=Decimal("4000"),
    )
    payload = card.model_dump_json()
    secure_action = next(action for action in card.actions if action.kind == "secure_file")

    assert card.statut_paiement == "partiel"
    assert card.montant_regle == Decimal("4000")
    assert card.restant_du == Decimal("8000")
    assert secure_action.api_path == f"/documents/{document.id}/fichier"
    assert "token" not in secure_action.api_path.lower()
    assert document.chemin_stockage not in payload


def test_journal_audit_est_refuse_aux_roles_non_administrateurs():
    plan = QueryPlan(
        domain=AssistantDomain.AUDIT,
        operation=QueryOperation.LIST,
        entity=QueryEntity.EVENEMENT_AUDIT,
    )

    with pytest.raises(assistant_query_engine.QueryEngineForbidden):
        assistant_query_engine._execute_rows(
            None,
            _user(RoleEnum.ASSISTANT),
            plan,
            uuid.uuid4(),
            None,
        )
