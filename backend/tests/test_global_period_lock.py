from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api import accounting as accounting_api
from app.api import documents as documents_api
from app.api import tva as tva_api
from app.core.database import get_db
from app.core.deps import get_current_user
from app.main import app
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.entreprise import Entreprise
from app.models.enums import (
    CategorieDocumentEnum,
    RoleEnum,
    StatutDocumentEnum,
    StatutValidationEnum,
    TypeEcritureEnum,
    TypeMouvementBancaireEnum,
)
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.rapprochement_bancaire_allocation import RapprochementBancaireAllocation
from app.models.tva_periode import TvaConfigurationEntreprise, TvaPeriode, TvaRegularisation
from app.models.workflow_comptable import PeriodeTravail


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_type, _compiler, **_kwargs):
    return "JSON"


@pytest.fixture()
def period_lock_api(monkeypatch, tmp_path):
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    for table in (
        Entreprise.__table__,
        Document.__table__,
        EcritureComptable.__table__,
        MouvementBancaire.__table__,
        RapprochementBancaireAllocation.__table__,
        TvaConfigurationEntreprise.__table__,
        TvaPeriode.__table__,
        TvaRegularisation.__table__,
        PeriodeTravail.__table__,
    ):
        table.create(engine)

    db = Session(engine)
    cabinet_id = uuid.uuid4()
    user = SimpleNamespace(
        id=uuid.uuid4(),
        cabinet_id=cabinet_id,
        role=RoleEnum.ADMIN_CABINET,
        email="admin@example.test",
        prenom="Admin",
        nom="Cabinet",
        is_active=True,
    )
    company = Entreprise(cabinet_id=cabinet_id, nom="Entreprise verrouillée", is_active=True)
    db.add(company)
    db.flush()

    def document(name: str) -> Document:
        path = tmp_path / name
        path.write_bytes(b"%PDF-1.4\n")
        item = Document(
            cabinet_id=cabinet_id,
            entreprise_id=company.id,
            uploaded_by=user.id,
            annee=2026,
            mois=8,
            categorie=CategorieDocumentEnum.ACHATS,
            nom_fichier_original=name,
            chemin_stockage=str(path),
            hash_fichier=uuid.uuid4().hex * 2,
            taille_octets=9,
            mime_type="application/pdf",
            statut=StatutDocumentEnum.TRAITE,
            donnees_extraites={"date_piece": "2026-08-10"},
        )
        db.add(item)
        db.flush()
        return item

    bank_document = document("banque.pdf")
    reprocess_document = document("retraiter.pdf")
    delete_document = document("supprimer.pdf")
    entry = EcritureComptable(
        cabinet_id=cabinet_id,
        entreprise_id=company.id,
        document_id=bank_document.id,
        type_ecriture=TypeEcritureEnum.ACHAT,
        numero_piece="FA-LOCK",
        date_piece=date(2026, 8, 10),
        tiers="Fournisseur",
        montant_ttc=Decimal("120.00"),
        statut_validation=StatutValidationEnum.PRETE_TOPAZE,
    )
    movement = MouvementBancaire(
        cabinet_id=cabinet_id,
        entreprise_id=company.id,
        document_id=bank_document.id,
        date_operation=date(2026, 8, 15),
        libelle="Règlement facture",
        type_mouvement=TypeMouvementBancaireEnum.DEBIT,
        montant=Decimal("120.00"),
    )
    vat_period = TvaPeriode(
        cabinet_id=cabinet_id,
        entreprise_id=company.id,
        annee=2026,
        mois=8,
        statut="provisoire",
        statut_comptable="prete_topaze",
        statut_declaration="prete_a_declarer",
        date_limite_declaration=date(2026, 9, 30),
    )
    work_period = PeriodeTravail(
        cabinet_id=cabinet_id,
        entreprise_id=company.id,
        exercice=2026,
        periode_debut=date(2026, 8, 1),
        periode_fin=date(2026, 8, 31),
        verrouillee=True,
    )
    db.add_all([entry, movement, vat_period, work_period])
    db.commit()

    calls = {"bank": 0, "recalc": 0, "validate_vat": 0, "task": 0}

    def propose_bank(_db, item):
        calls["bank"] += 1
        item.statut_rapprochement = "propose"

    def recalc(_db, **_kwargs):
        calls["recalc"] += 1
        return []

    def validate_vat(_db, *, periode, **_kwargs):
        calls["validate_vat"] += 1
        periode.statut = "validee"

    monkeypatch.setattr(accounting_api.rapprochement_bancaire_service, "rapprocher_mouvement", propose_bank)
    monkeypatch.setattr(
        accounting_api.ligne_comptable_service,
        "synchroniser_lignes_banque",
        lambda *_args, **_kwargs: SimpleNamespace(applicable=False, complet=True, raisons=[], lignes=[]),
    )
    monkeypatch.setattr(tva_api.tva_comptable_service, "recalculer_periodes_tva", recalc)
    monkeypatch.setattr(tva_api.tva_comptable_service, "valider_periode_tva", validate_vat)
    monkeypatch.setattr(documents_api.process_document, "delay", lambda *_args: calls.__setitem__("task", calls["task"] + 1))
    monkeypatch.setattr(accounting_api.audit_service, "enregistrer", lambda *_args, **_kwargs: None)

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: user
    client = TestClient(app)
    yield SimpleNamespace(
        client=client,
        db=db,
        user=user,
        company=company,
        entry=entry,
        movement=movement,
        vat_period=vat_period,
        work_period=work_period,
        bank_document=bank_document,
        reprocess_document=reprocess_document,
        delete_document=delete_document,
        calls=calls,
    )
    client.close()
    app.dependency_overrides.clear()
    db.close()
    engine.dispose()


def test_rapprochement_bancaire_refuse_sur_periode_verrouillee(period_lock_api):
    ctx = period_lock_api
    before = ctx.movement.statut_rapprochement
    response = ctx.client.post(f"/accounting/bank-movements/{ctx.movement.id}/reconcile-auto")
    assert response.status_code == 409
    assert "lecture seule" in response.json()["detail"]
    ctx.db.refresh(ctx.movement)
    assert ctx.movement.statut_rapprochement == before
    assert ctx.calls["bank"] == 0


@pytest.mark.parametrize(
    ("method", "path_factory", "payload_factory"),
    [
        (
            "PATCH",
            lambda ctx: f"/accounting/bank-movements/{ctx.movement.id}/reconcile/{ctx.entry.id}",
            lambda _ctx: None,
        ),
        (
            "DELETE",
            lambda ctx: f"/accounting/bank-movements/{ctx.movement.id}/reconcile",
            lambda _ctx: None,
        ),
        (
            "POST",
            lambda ctx: f"/accounting/bank-movements/{ctx.movement.id}/allocations",
            lambda ctx: {"allocations": [{"ecriture_id": str(ctx.entry.id), "montant_affecte": "120.00"}]},
        ),
        (
            "PATCH",
            lambda ctx: f"/accounting/bank-movements/{ctx.movement.id}/operation",
            lambda _ctx: {"nature_operation": "autre"},
        ),
        (
            "PATCH",
            lambda ctx: f"/accounting/bank-movements/{ctx.movement.id}/internal-transfer/{ctx.movement.id}",
            lambda _ctx: None,
        ),
        (
            "PATCH",
            lambda ctx: f"/documents/{ctx.bank_document.id}/mouvements/{ctx.movement.id}",
            lambda _ctx: {"libelle": "Libellé corrigé"},
        ),
    ],
)
def test_toutes_les_mutations_bancaires_refusent_le_verrouillage(
    period_lock_api, method, path_factory, payload_factory
):
    ctx = period_lock_api
    payload = payload_factory(ctx)
    response = ctx.client.request(method, path_factory(ctx), json=payload)
    assert response.status_code == 409


@pytest.mark.parametrize(
    ("path_suffix", "payload"),
    [
        ("saisie-topaze", {"saisie": True, "reference_lot": "LOT-1"}),
        (
            "declarer",
            {
                "date_declaration": "2026-09-20",
                "reference": "TVA-08-2026",
                "note": "Déclaration contrôlée",
            },
        ),
    ],
)
def test_statuts_tva_comptable_et_declaration_refuses_sur_periode_verrouillee(
    period_lock_api, path_suffix, payload
):
    ctx = period_lock_api
    method = "PATCH" if path_suffix == "saisie-topaze" else "POST"
    response = ctx.client.request(
        method,
        f"/accounting/tva-v2/periodes/{ctx.vat_period.id}/{path_suffix}",
        params={"entreprise_id": str(ctx.company.id)},
        json=payload,
    )
    assert response.status_code == 409


def test_regularisation_tva_refusee_sur_periode_verrouillee(period_lock_api):
    ctx = period_lock_api
    response = ctx.client.post(
        f"/accounting/tva-v2/periodes/{ctx.vat_period.id}/regularisations",
        params={"entreprise_id": str(ctx.company.id)},
        json={
            "nature": "correction",
            "montant": "25.00",
            "sens": "augmentation",
            "motif": "Correction contrôlée",
            "date_regularisation": "2026-08-20",
            "valider": True,
            "source": "manuel",
        },
    )
    assert response.status_code == 409
    assert ctx.db.execute(select(TvaRegularisation)).scalars().all() == []


def test_recalcul_tva_refuse_sur_periode_verrouillee(period_lock_api):
    ctx = period_lock_api
    response = ctx.client.post(
        "/accounting/tva-v2/recalculer",
        params={"entreprise_id": str(ctx.company.id), "annee": 2026},
    )
    assert response.status_code == 409
    assert ctx.calls["recalc"] == 0


def test_validation_tva_refusee_sur_periode_verrouillee(period_lock_api):
    ctx = period_lock_api
    response = ctx.client.post(
        f"/accounting/tva-v2/periodes/{ctx.vat_period.id}/valider",
        params={"entreprise_id": str(ctx.company.id)},
    )
    assert response.status_code == 409
    assert ctx.calls["validate_vat"] == 0
    ctx.db.refresh(ctx.vat_period)
    assert ctx.vat_period.statut == "provisoire"


def test_modification_echeance_refusee_sans_changement_partiel(period_lock_api):
    ctx = period_lock_api
    before = ctx.vat_period.date_limite_declaration
    response = ctx.client.patch(
        f"/accounting/tva-v2/periodes/{ctx.vat_period.id}/echeance",
        params={"entreprise_id": str(ctx.company.id)},
        json={"date_limite": "2026-10-31"},
    )
    assert response.status_code == 409
    ctx.db.expire_all()
    stored = ctx.db.get(TvaPeriode, ctx.vat_period.id)
    assert stored.date_limite_declaration == before


def test_retraitement_document_refuse_et_aucune_tache_lancee(period_lock_api):
    ctx = period_lock_api
    before = ctx.reprocess_document.statut
    response = ctx.client.post(f"/documents/{ctx.reprocess_document.id}/retraiter")
    assert response.status_code == 409
    ctx.db.refresh(ctx.reprocess_document)
    assert ctx.reprocess_document.statut == before
    assert ctx.calls["task"] == 0


def test_suppression_document_refusee_sur_periode_verrouillee(period_lock_api):
    ctx = period_lock_api
    response = ctx.client.delete(
        f"/documents/{ctx.delete_document.id}",
        params={"supprimer_fichier": False},
    )
    assert response.status_code == 409
    assert ctx.db.get(Document, ctx.delete_document.id) is not None


def test_reouverture_valide_reautorise_les_memes_mutations(period_lock_api):
    ctx = period_lock_api
    reopened = ctx.client.post(
        f"/accounting/workflow/periodes/{ctx.work_period.id}/reouvrir",
        params={"entreprise_id": str(ctx.company.id)},
        json={"justification": "Correction métier autorisée"},
    )
    assert reopened.status_code == 200
    assert reopened.json()["verrouillee"] is False

    bank = ctx.client.post(f"/accounting/bank-movements/{ctx.movement.id}/reconcile-auto")
    assert bank.status_code == 200
    regularisation = ctx.client.post(
        f"/accounting/tva-v2/periodes/{ctx.vat_period.id}/regularisations",
        params={"entreprise_id": str(ctx.company.id)},
        json={
            "nature": "correction",
            "montant": "25.00",
            "sens": "augmentation",
            "motif": "Correction contrôlée",
            "date_regularisation": "2026-08-20",
            "valider": True,
            "source": "manuel",
        },
    )
    assert regularisation.status_code == 200
    assert ctx.client.post(
        "/accounting/tva-v2/recalculer",
        params={"entreprise_id": str(ctx.company.id), "annee": 2026},
    ).status_code == 200
    assert ctx.client.post(
        f"/accounting/tva-v2/periodes/{ctx.vat_period.id}/valider",
        params={"entreprise_id": str(ctx.company.id)},
    ).status_code == 200
    assert ctx.client.patch(
        f"/accounting/tva-v2/periodes/{ctx.vat_period.id}/echeance",
        params={"entreprise_id": str(ctx.company.id)},
        json={"date_limite": "2026-10-31"},
    ).status_code == 200
    assert ctx.client.post(f"/documents/{ctx.reprocess_document.id}/retraiter").status_code == 200
    assert ctx.client.delete(
        f"/documents/{ctx.delete_document.id}", params={"supprimer_fichier": False}
    ).status_code == 200
    assert ctx.calls == {"bank": 1, "recalc": 1, "validate_vat": 1, "task": 1}


def test_get_reste_autorise_sur_periode_verrouillee(period_lock_api):
    ctx = period_lock_api
    response = ctx.client.get(
        "/accounting/workflow/periodes",
        params={"entreprise_id": str(ctx.company.id), "exercice": 2026},
    )
    assert response.status_code == 200
    assert response.json()[0]["verrouillee"] is True


def test_refus_successifs_ne_laissent_aucune_modification_partielle(period_lock_api):
    ctx = period_lock_api
    deadline = ctx.vat_period.date_limite_declaration
    status = ctx.movement.statut_rapprochement
    assert ctx.client.post(f"/accounting/bank-movements/{ctx.movement.id}/reconcile-auto").status_code == 409
    assert ctx.client.patch(
        f"/accounting/tva-v2/periodes/{ctx.vat_period.id}/echeance",
        params={"entreprise_id": str(ctx.company.id)},
        json={"date_limite": "2026-12-31"},
    ).status_code == 409
    assert ctx.client.post(f"/documents/{ctx.reprocess_document.id}/retraiter").status_code == 409
    ctx.db.expire_all()
    assert ctx.db.get(MouvementBancaire, ctx.movement.id).statut_rapprochement == status
    assert ctx.db.get(TvaPeriode, ctx.vat_period.id).date_limite_declaration == deadline
    assert ctx.db.get(Document, ctx.reprocess_document.id).statut == StatutDocumentEnum.TRAITE
    assert ctx.calls == {"bank": 0, "recalc": 0, "validate_vat": 0, "task": 0}
