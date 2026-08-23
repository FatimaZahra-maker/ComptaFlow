from types import SimpleNamespace
import uuid

import pytest

from app.services import company_service


def _entity(cabinet_id, name, *, ice=None, automatic=False):
    return SimpleNamespace(
        id=uuid.uuid4(),
        cabinet_id=cabinet_id,
        nom=name,
        ice=ice,
        identifiant_fiscal=None,
        rc=None,
        is_active=True,
        creee_automatiquement=automatic,
    )


@pytest.fixture
def tenant_context(monkeypatch):
    cabinet_id = uuid.uuid4()
    other_cabinet_id = uuid.uuid4()
    cabinet = SimpleNamespace(
        id=cabinet_id,
        nom="SEGURIBAT",
        ice="001122334455667",
        is_active=True,
    )
    other_cabinet = SimpleNamespace(
        id=other_cabinet_id,
        nom="AUTRE CABINET",
        ice="009999999999999",
        is_active=True,
    )
    anzobat = _entity(cabinet_id, "ANZOBAT", ice="009988776655443")
    foreign_anzobat = _entity(other_cabinet_id, "ANZOBAT", ice="007777777777777")
    placeholder = _entity(cabinet_id, "Entreprise à identifier", automatic=True)
    foreign_placeholder = _entity(other_cabinet_id, "Entreprise à identifier", automatic=True)

    cabinets = {cabinet_id: cabinet, other_cabinet_id: other_cabinet}
    companies = {
        cabinet_id: [anzobat],
        other_cabinet_id: [foreign_anzobat],
    }
    placeholders = {
        cabinet_id: placeholder,
        other_cabinet_id: foreign_placeholder,
    }
    monkeypatch.setattr(
        company_service,
        "_charger_cabinet",
        lambda _db, requested: cabinets.get(requested),
    )
    monkeypatch.setattr(
        company_service,
        "_entreprises_suivies",
        lambda _db, requested: list(companies.get(requested, [])),
    )
    monkeypatch.setattr(
        company_service,
        "_obtenir_placeholder",
        lambda _db, requested: placeholders[requested],
    )
    return SimpleNamespace(
        cabinet_id=cabinet_id,
        other_cabinet_id=other_cabinet_id,
        anzobat=anzobat,
        foreign_anzobat=foreign_anzobat,
        placeholder=placeholder,
        foreign_placeholder=foreign_placeholder,
    )


def _identify(context, data, *, cabinet_id=None):
    return company_service.identifier_entreprise_et_direction(
        None,
        cabinet_id or context.cabinet_id,
        data,
    )


def test_seguribat_vers_anzobat_est_un_achat(tenant_context):
    data = {
        "type_document": "facture",
        "nom_fournisseur": "SEGURIBAT",
        "nom_client": "ANZOBAT",
    }

    company, direction, third_party = _identify(tenant_context, data)

    assert company is tenant_context.anzobat
    assert direction == "achats"
    assert third_party == "SEGURIBAT"
    assert data["implique_cabinet"] is True
    assert data["role_cabinet"] == "fournisseur"


def test_anzobat_vers_seguribat_est_une_vente(tenant_context):
    data = {
        "type_document": "facture",
        "nom_fournisseur": "ANZOBAT",
        "nom_client": "SEGURIBAT",
    }

    company, direction, third_party = _identify(tenant_context, data)

    assert company is tenant_context.anzobat
    assert direction == "ventes"
    assert third_party == "SEGURIBAT"
    assert data["role_cabinet"] == "client"


def test_document_tourne_conserve_les_roles_du_fallback_ocr(tenant_context):
    data = {
        "type_document": "facture",
        "orientation_document": 180,
        "nom_entreprise": "SEGURIBAT",
        "tiers": "ANZOBAT",
    }

    company, direction, third_party = _identify(tenant_context, data)

    assert company is tenant_context.anzobat
    assert direction == "achats"
    assert third_party == "SEGURIBAT"


def test_variation_ocr_normalisee_du_nom_seguribat(tenant_context):
    data = {
        "type_document": "facture",
        "nom_fournisseur": "SÉGURI-BAT SARL",
        "nom_client": "ANZOBAT",
    }

    company, direction, third_party = _identify(tenant_context, data)

    assert company is tenant_context.anzobat
    assert direction == "achats"
    assert third_party == "SÉGURI-BAT SARL"
    assert data["implique_cabinet"] is True


def test_sans_entreprise_suivie_identifiable_reste_a_verifier(
    tenant_context,
    monkeypatch,
):
    monkeypatch.setattr(
        company_service,
        "_entreprises_suivies",
        lambda _db, _cabinet_id: [],
    )
    data = {
        "type_document": "facture",
        "nom_fournisseur": "FOURNISSEUR EXTERNE",
        "nom_client": "CLIENT INCONNU",
    }

    company, direction, third_party = _identify(tenant_context, data)

    assert company is tenant_context.placeholder
    assert direction is None
    assert third_party == "CLIENT INCONNU"
    assert data["direction_a_verifier"] is True


def test_isolation_cabinet_id_interdit_anzobat_d_un_autre_cabinet(
    tenant_context,
    monkeypatch,
):
    monkeypatch.setattr(
        company_service,
        "_entreprises_suivies",
        lambda _db, requested: (
            [tenant_context.foreign_anzobat]
            if requested == tenant_context.other_cabinet_id
            else []
        ),
    )
    data = {
        "type_document": "facture",
        "nom_fournisseur": "SEGURIBAT",
        "nom_client": "ANZOBAT",
    }

    company, direction, _third_party = _identify(tenant_context, data)

    assert company is None
    assert company is not tenant_context.foreign_anzobat
    assert direction is None
    assert data["traitement_cabinet_propre"] is True
    assert data["direction_a_verifier"] is True
