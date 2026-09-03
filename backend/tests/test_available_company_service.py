from datetime import date
from types import SimpleNamespace
import uuid

import pytest

from app.models.enums import (
    CategorieDocumentEnum,
    StatutValidationEnum,
    TypeEcritureEnum,
)
from app.services.available_company_service import (
    construire_requete,
    lister_entreprises_disponibles,
)
from app.schemas.entreprise import EntrepriseDisponibleOut


def compiled(module, *, exercice=None):
    cabinet_id = uuid.uuid4()
    statement = construire_requete(
        cabinet_id=cabinet_id,
        module=module,
        exercice=exercice,
    )
    result = statement.compile()
    return str(result), result.params, cabinet_id


def values(params):
    return list(params.values())


def test_entreprise_achat_apparait_via_document_ou_ecriture_achat():
    sql, params, _ = compiled("achats")
    assert "ecritures_comptables" in sql
    assert "documents" in sql
    assert TypeEcritureEnum.ACHAT in values(params)
    assert CategorieDocumentEnum.ACHATS in next(
        value for value in values(params) if isinstance(value, list)
    )


def test_entreprise_sans_achat_n_est_pas_rendue_disponible_par_une_vente():
    _sql, params, _ = compiled("achats")
    assert TypeEcritureEnum.VENTE not in values(params)
    assert CategorieDocumentEnum.VENTES not in [
        item for value in values(params) if isinstance(value, list) for item in value
    ]


def test_entreprise_vente_apparait_via_document_ou_ecriture_vente():
    sql, params, _ = compiled("ventes")
    assert "ecritures_comptables" in sql and "documents" in sql
    assert TypeEcritureEnum.VENTE in values(params)


def test_entreprise_avec_mouvement_apparait_dans_banque():
    sql, _params, _ = compiled("banque")
    assert "mouvements_bancaires" in sql
    assert "documents" in sql


def test_nom_de_banque_auto_cree_ne_devient_pas_entreprise_geree():
    sql, _params, _ = compiled("banque")
    assert "entreprises.creee_automatiquement IS false" in sql
    assert "entreprises.is_active IS true" in sql


def test_ecriture_brouillon_ouvre_le_selecteur_registres():
    sql, params, _ = compiled("registres")
    statuses = next(value for value in values(params) if isinstance(value, (list, tuple)))
    assert StatutValidationEnum.BROUILLON in statuses
    assert StatutValidationEnum.A_VERIFIER in statuses
    assert StatutValidationEnum.VALIDE in statuses
    assert "statut_validation" in sql


def test_registre_officiel_reste_filtre_sur_valide():
    # Le sélecteur accepte trois statuts mais la requête officielle existante
    # dans accounting.get_registre conserve explicitement VALIDE.
    from app.api import accounting

    class Result:
        def all(self):
            return []

    class Db:
        statement = None

        def execute(self, statement):
            self.statement = statement
            return Result()

    db = Db()
    user = SimpleNamespace(cabinet_id=uuid.uuid4())
    response = accounting.get_registre(
        entreprise_id=uuid.uuid4(),
        categorie=CategorieDocumentEnum.ACHATS,
        annee=2026,
        mois=1,
        trimestre=None,
        db=db,
        current_user=user,
    )
    query = db.statement.compile()
    assert StatutValidationEnum.VALIDE in query.params.values()
    assert response.nombre == 0


@pytest.mark.parametrize("module", ["ledger", "balance"])
def test_entreprise_avec_lignes_apparait_grand_livre_et_balance(module):
    sql, _params, _ = compiled(module)
    assert "lignes_comptables" in sql
    assert "lignes_comptables.entreprise_id = entreprises.id" in sql


def test_entreprise_sans_donnee_du_module_est_exclue_par_exists():
    sql, _params, _ = compiled("ecritures")
    assert "EXISTS (SELECT 1" in sql
    assert "ecritures_comptables.entreprise_id = entreprises.id" in sql


def test_isolation_cabinet_id_est_appliquee_a_toutes_les_sources():
    sql, params, cabinet_id = compiled("achats")
    assert sql.count("cabinet_id") >= 3
    assert sum(value == cabinet_id for value in values(params)) == 3


def test_isolation_entreprise_id_est_correlee_sur_le_dossier_gere():
    sql, _params, _ = compiled("comptes_bancaires")
    assert sql.count("entreprise_id = entreprises.id") == 3
    assert "comptes_bancaires_entreprise" in sql


def test_exercice_est_pris_en_compte_pour_cpc():
    _sql_2025, params_2025, _ = compiled("cpc", exercice=2025)
    _sql_2026, params_2026, _ = compiled("cpc", exercice=2026)
    assert date(2025, 1, 1) in values(params_2025)
    assert date(2025, 12, 31) in values(params_2025)
    assert date(2026, 1, 1) in values(params_2026)
    assert date(2026, 12, 31) in values(params_2026)


def test_exercice_obligatoire_pour_module_dependant():
    with pytest.raises(ValueError, match="exercice est obligatoire"):
        construire_requete(cabinet_id=uuid.uuid4(), module="tva")


def test_compteurs_registres_sont_agreges_sans_n_plus_un():
    entreprise_id = uuid.uuid4()
    company = SimpleNamespace(
        id=entreprise_id,
        nom="Entreprise test",
        ice=None,
        is_active=True,
        creee_automatiquement=False,
    )

    class CompanyResult:
        def scalars(self):
            return self

        def all(self):
            return [company]

    class CountResult:
        def all(self):
            return [
                (entreprise_id, StatutValidationEnum.BROUILLON, 2),
                (entreprise_id, StatutValidationEnum.A_VERIFIER, 3),
                (entreprise_id, StatutValidationEnum.VALIDE, 5),
            ]

    class Db:
        def __init__(self):
            self.calls = 0

        def execute(self, _statement):
            self.calls += 1
            return CompanyResult() if self.calls == 1 else CountResult()

    db = Db()
    rows = lister_entreprises_disponibles(
        db,
        cabinet_id=uuid.uuid4(),
        module="registres",
    )

    assert db.calls == 2
    assert len(rows) == 1
    assert rows[0].ecritures_brouillon == 2
    assert rows[0].ecritures_a_verifier == 3
    assert rows[0].ecritures_validees == 5
    assert EntrepriseDisponibleOut.model_validate(rows[0]).is_active is True
