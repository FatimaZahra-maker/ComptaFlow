from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.orm import Session

from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.enums import (
    CategorieDocumentEnum, StatutDocumentEnum, StatutValidationEnum,
    TauxTVAEnum, TypeEcritureEnum,
)
from app.models.entreprise import Entreprise
from app.models.ligne_comptable import LigneComptable
from app.models.tva_periode import TvaConfigurationEntreprise, TvaPeriode
from app.models.workflow_comptable import AnomalieComptable, PeriodeTravail
from app.services import tva_comptable_service, workflow_comptable_service


@compiles(JSONB, "sqlite")
def _compile_jsonb_for_sqlite(_type, _compiler, **_kwargs):
    """Les tests unitaires isolés utilisent SQLite, la production PostgreSQL."""
    return "JSON"


@pytest.fixture()
def db(monkeypatch):
    engine = create_engine("sqlite+pysqlite:///:memory:")
    for table in (
        Entreprise.__table__, Document.__table__, EcritureComptable.__table__,
        TvaConfigurationEntreprise.__table__, TvaPeriode.__table__,
        CompteComptableEntreprise.__table__, LigneComptable.__table__,
        AnomalieComptable.__table__, PeriodeTravail.__table__,
    ):
        table.create(engine)
    monkeypatch.setattr(workflow_comptable_service.audit_service, "enregistrer", lambda *args, **kwargs: None)
    with Session(engine) as session:
        yield session
    engine.dispose()


def _entry(db: Session, *, ttc="120.00", tva_account="34552"):
    cabinet_id, uploader_id = uuid.uuid4(), uuid.uuid4()
    company = Entreprise(cabinet_id=cabinet_id, nom="Entreprise test", is_active=True)
    db.add(company); db.flush()
    document = Document(
        cabinet_id=cabinet_id, entreprise_id=company.id, uploaded_by=uploader_id,
        annee=2026, mois=8, categorie=CategorieDocumentEnum.ACHATS,
        nom_fichier_original="facture.pdf", chemin_stockage="private/facture.pdf",
        hash_fichier=uuid.uuid4().hex * 2, statut=StatutDocumentEnum.TRAITE,
        donnees_extraites={"confiance_globale": "0.95"},
    )
    db.add(document); db.flush()
    entry = EcritureComptable(
        cabinet_id=cabinet_id, entreprise_id=company.id, document_id=document.id,
        type_ecriture=TypeEcritureEnum.ACHAT, numero_piece="FA-1", date_piece=date(2026, 8, 1),
        tiers="Fournisseur", compte_tiers="441100", compte_ht="611100", compte_tva=tva_account,
        montant_ht=Decimal("100.00"), montant_tva=Decimal("20.00"), montant_ttc=Decimal(ttc),
        taux_tva=TauxTVAEnum.TAUX_20, statut_validation=StatutValidationEnum.CALCUL_EN_COURS,
    )
    db.add(entry)
    for number, usage in (("441100", "fournisseur"), ("611100", "ht"), ("34552", "tva")):
        db.add(CompteComptableEntreprise(
            cabinet_id=cabinet_id, entreprise_id=company.id, numero_compte=number,
            libelle=number, type_usage=usage, is_active=True,
        ))
    db.flush()
    return entry, document


def test_ecriture_equilibree_devient_automatiquement_prete_topaze(db):
    entry, document = _entry(db)
    anomalies = workflow_comptable_service.controler_et_transitionner(db, entry, document=document)
    assert anomalies == []
    assert entry.statut_validation == StatutValidationEnum.PRETE_TOPAZE
    assert entry.ready_for_topaze_at is not None
    lines = db.execute(select(LigneComptable).where(LigneComptable.ecriture_id == entry.id)).scalars().all()
    assert sum((line.debit for line in lines), Decimal("0")) == sum((line.credit for line in lines), Decimal("0"))
    assert all(line.est_validee for line in lines)


def test_ht_tva_ttc_incoherent_passe_a_verifier_et_trace_anomalie(db):
    entry, document = _entry(db, ttc="121.00")
    anomalies = workflow_comptable_service.controler_et_transitionner(db, entry, document=document)
    assert entry.statut_validation == StatutValidationEnum.A_VERIFIER
    assert "montants_incoherents" in {item["type"] for item in anomalies}
    stored = db.execute(select(AnomalieComptable).where(AnomalieComptable.ecriture_id == entry.id)).scalars().all()
    assert any(item.type_anomalie == "montants_incoherents" and item.resolved_at is None for item in stored)


def test_compte_tva_introuvable_bloque_la_preparation(db):
    entry, document = _entry(db, tva_account="345599")
    anomalies = workflow_comptable_service.controler_et_transitionner(db, entry, document=document)
    assert entry.statut_validation == StatutValidationEnum.A_VERIFIER
    assert "compte_hors_plan" in {item["type"] for item in anomalies}


def test_doublon_potentiel_ne_contamine_pas_les_etats(db):
    entry, document = _entry(db)
    entry.doublon_potentiel_id = uuid.uuid4()
    workflow_comptable_service.controler_et_transitionner(db, entry, document=document)
    assert entry.statut_validation == StatutValidationEnum.A_VERIFIER
    assert not any(line.est_validee for line in db.execute(select(LigneComptable)).scalars())


def test_correction_relance_tous_les_controles_et_resout_les_anomalies(db):
    entry, document = _entry(db, ttc="121.00")
    workflow_comptable_service.controler_et_transitionner(db, entry, document=document)
    entry.montant_ttc = Decimal("120.00")
    workflow_comptable_service.controler_et_transitionner(db, entry, document=document)
    assert entry.statut_validation == StatutValidationEnum.PRETE_TOPAZE
    previous = db.execute(select(AnomalieComptable).where(AnomalieComptable.ecriture_id == entry.id)).scalars().all()
    assert previous and all(item.resolved_at is not None for item in previous)


def test_periode_verrouillee_refuse_une_correction(db):
    entry, _ = _entry(db)
    db.add(PeriodeTravail(
        cabinet_id=entry.cabinet_id, entreprise_id=entry.entreprise_id, exercice=2026,
        periode_debut=date(2026, 1, 1), periode_fin=date(2026, 12, 31), verrouillee=True,
    ))
    db.flush()
    with pytest.raises(ValueError, match="verrouillée"):
        workflow_comptable_service.verifier_periode_modifiable(db, entry)


def test_date_future_est_signalee_sans_correction_silencieuse(db):
    entry, document = _entry(db)
    entry.date_piece = date.today() + timedelta(days=1)
    anomalies = workflow_comptable_service.controler_et_transitionner(db, entry, document=document)
    assert "date_future" in {item["type"] for item in anomalies}
    assert entry.date_piece == date.today() + timedelta(days=1)


def test_centralisation_tva_utilise_uniquement_les_comptes_configures_et_reste_equilibree(db):
    entry, _ = _entry(db)
    for number in ("445500", "345520", "445600"):
        db.add(CompteComptableEntreprise(
            cabinet_id=entry.cabinet_id,
            entreprise_id=entry.entreprise_id,
            numero_compte=number,
            libelle=number,
            type_usage="tva",
            is_active=True,
        ))
    configuration = TvaConfigurationEntreprise(
        cabinet_id=entry.cabinet_id,
        entreprise_id=entry.entreprise_id,
        periodicite="mensuelle",
        prorata_applicable=False,
        retenue_applicable=False,
        compte_tva_collectee="445500",
        compte_tva_recuperable_charges="345520",
        compte_tva_a_payer="445600",
    )
    period = TvaPeriode(
        cabinet_id=entry.cabinet_id,
        entreprise_id=entry.entreprise_id,
        annee=2026,
        mois=8,
        tva_collectee=Decimal("200.00"),
        tva_recuperable_charges=Decimal("50.00"),
        tva_recuperable_immobilisations=Decimal("0.00"),
        credit_anterieur=Decimal("0.00"),
        regularisations=Decimal("0.00"),
        retenues_tva=Decimal("0.00"),
        tva_nette=Decimal("150.00"),
        tva_a_payer=Decimal("150.00"),
        credit_a_reporter=Decimal("0.00"),
        anomalies=[],
    )
    db.add_all([configuration, period])
    db.flush()

    anomalies = tva_comptable_service.synchroniser_ecriture_tva(
        db,
        periode=period,
        configuration=configuration,
    )
    lines = db.execute(select(LigneComptable).where(
        LigneComptable.tva_periode_id == period.id,
    )).scalars().all()
    assert anomalies == []
    assert {line.compte for line in lines} == {"445500", "345520", "445600"}
    assert sum((line.debit for line in lines), Decimal("0")) == sum((line.credit for line in lines), Decimal("0"))
    assert all(line.est_validee and line.origine == "tva" for line in lines)


def test_centralisation_tva_sans_compte_exact_reste_a_verifier_sans_ligne(db):
    entry, _ = _entry(db)
    configuration = TvaConfigurationEntreprise(
        cabinet_id=entry.cabinet_id,
        entreprise_id=entry.entreprise_id,
        periodicite="mensuelle",
        prorata_applicable=False,
        retenue_applicable=False,
    )
    period = TvaPeriode(
        cabinet_id=entry.cabinet_id,
        entreprise_id=entry.entreprise_id,
        annee=2026,
        mois=9,
        tva_collectee=Decimal("100.00"),
        tva_recuperable_charges=Decimal("0.00"),
        tva_recuperable_immobilisations=Decimal("0.00"),
        credit_anterieur=Decimal("0.00"),
        regularisations=Decimal("0.00"),
        retenues_tva=Decimal("0.00"),
        tva_nette=Decimal("100.00"),
        tva_a_payer=Decimal("100.00"),
        credit_a_reporter=Decimal("0.00"),
        anomalies=[],
    )
    db.add_all([configuration, period])
    db.flush()
    anomalies = tva_comptable_service.synchroniser_ecriture_tva(
        db,
        periode=period,
        configuration=configuration,
    )
    assert anomalies
    assert db.execute(select(LigneComptable).where(
        LigneComptable.tva_periode_id == period.id,
    )).scalars().all() == []
