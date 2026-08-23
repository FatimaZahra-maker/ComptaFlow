from datetime import date
from decimal import Decimal

import pytest

from app.models.enums import TypeEcritureEnum
from app.services import exchange_rate_service as fx


HTML_BAM = """
<html>
  <body>
    <input id="date" name="date" value="15/05/2026" />
    <table>
      <tr>
        <th>Currencies</th>
        <th>Purchase from customers</th>
        <th>Sale to customers</th>
      </tr>
      <tr><td>1 EURO</td><td>10.2947</td><td>11.9641</td></tr>
      <tr><td>1 US DOLLAR</td><td>8.70440</td><td>10.1160</td></tr>
      <tr><td>100 JAPANESE YEN</td><td>5.56410</td><td>6.46630</td></tr>
    </table>
  </body>
</html>
"""


def test_normaliser_devise_aliases():
    assert fx.normaliser_devise("EUR") == "EUR"
    assert fx.normaliser_devise("Euro") == "EUR"
    assert fx.normaliser_devise("$ ") == "USD"
    assert fx.normaliser_devise("dirham marocain") == "MAD"


def test_parser_page_bam_preserve_rate_and_jpy_unit():
    rows = fx._parser_page_bam(HTML_BAM, date(2026, 5, 15))
    eur = next(row for row in rows if row["devise"] == "EUR")
    jpy = next(row for row in rows if row["devise"] == "JPY")

    assert eur["cours_achat"] == Decimal("10.2947")
    assert eur["cours_vente"] == Decimal("11.9641")
    assert eur["unite_cotation"] == 1
    assert jpy["unite_cotation"] == 100
    assert jpy["cours_vente"] == Decimal("6.46630")


def test_parser_refuses_wrong_date():
    with pytest.raises(fx.TauxChangeIndisponible):
        fx._parser_page_bam(HTML_BAM, date(2026, 5, 16))


def test_conversion_uses_full_precision():
    result = fx.convertir_montant_mad(
        Decimal("1500"),
        Decimal("11.9641"),
        1,
    )
    assert result == Decimal("17946.15")


def test_conversion_jpy_divides_by_100():
    result = fx.convertir_montant_mad(
        Decimal("10000"),
        Decimal("6.46630"),
        100,
    )
    assert result == Decimal("646.63")


def _fake_rate() -> fx.TauxChangeResultat:
    return fx.TauxChangeResultat(
        date_cours=date(2026, 5, 15),
        devise="EUR",
        unite_cotation=1,
        libelle_bam="1 EURO",
        cours_achat=Decimal("10.2947"),
        cours_vente=Decimal("11.9641"),
        source=fx.SOURCE_BAM_BILLETS,
        source_url="https://example.test/bam",
        depuis_cache=False,
    )


def test_facture_achat_uses_vente_clientele(monkeypatch):
    monkeypatch.setattr(fx, "obtenir_taux_bam", lambda db, d, c: _fake_rate())
    donnees = {
        "date_piece": "2026-05-15",
        "devise": "EUR",
        "montant_ht": 1000,
        "montant_tva": 200,
        "montant_ttc": 1200,
    }

    result = fx.preparer_facture_pour_comptabilite(
        object(),
        donnees,
        type_ecriture=TypeEcritureEnum.ACHAT.value,
    )

    assert result.conversion_effectuee is True
    assert donnees["type_cours_change"] == "vente_clientele"
    assert donnees["taux_change"] == "11.9641"
    assert result.donnees_comptables["montant_ttc"] == Decimal("14356.92")


def test_facture_vente_uses_achat_clientele(monkeypatch):
    monkeypatch.setattr(fx, "obtenir_taux_bam", lambda db, d, c: _fake_rate())
    donnees = {
        "date_piece": "2026-05-15",
        "devise": "EUR",
        "montant_ttc": 2500,
    }

    result = fx.preparer_facture_pour_comptabilite(
        object(),
        donnees,
        type_ecriture=TypeEcritureEnum.VENTE.value,
    )

    assert donnees["type_cours_change"] == "achat_clientele"
    assert donnees["taux_change"] == "10.2947"
    assert result.donnees_comptables["montant_ttc"] == Decimal("25736.75")


def test_bank_debit_and_credit_choose_opposite_sides(monkeypatch):
    monkeypatch.setattr(fx, "obtenir_taux_bam", lambda db, d, c: _fake_rate())

    debit = fx.convertir_mouvement_bancaire(
        object(),
        date_operation=date(2026, 5, 15),
        devise="EUR",
        type_mouvement="debit",
        montant=Decimal("100"),
    )
    credit = fx.convertir_mouvement_bancaire(
        object(),
        date_operation=date(2026, 5, 15),
        devise="EUR",
        type_mouvement="credit",
        montant=Decimal("100"),
    )

    assert debit.type_cours_change == "vente_clientele"
    assert debit.taux_change == Decimal("11.9641")
    assert debit.montant_mad == Decimal("1196.41")
    assert credit.type_cours_change == "achat_clientele"
    assert credit.taux_change == Decimal("10.2947")
    assert credit.montant_mad == Decimal("1029.47")


def test_bank_actual_mad_amount_is_preserved_over_theoretical_rate(monkeypatch):
    monkeypatch.setattr(fx, "obtenir_taux_bam", lambda *args, **kwargs: _fake_rate())
    result = fx.convertir_mouvement_bancaire(
        object(),
        date_operation=date(2026, 5, 15),
        devise="EUR",
        type_mouvement="debit",
        montant=Decimal("1000.00"),
        montant_mad_reel=Decimal("12010.35"),
    )
    assert result.montant_mad == Decimal("12010.35")
    assert result.montant_mad_theorique == Decimal("11964.10")
    assert result.montant_mad_source == "banque"
