"""app/services/exchange_rate_service.py

Moteur de devises transversal de ComptaFlow.

Source V1 : Bank Al-Maghrib, tableau « Foreign banknotes exchange rate »
(cours des billets de banque étrangers), qui expose :
- Purchase from customers = achat auprès de la clientèle ;
- Sale to customers     = vente à la clientèle.

Règle métier du cabinet :
- facture ACHAT en devise  -> cours VENTE à la clientèle ;
- facture VENTE en devise  -> cours ACHAT auprès de la clientèle ;
- mouvement BANQUE débit   -> cours VENTE à la clientèle ;
- mouvement BANQUE crédit  -> cours ACHAT auprès de la clientèle.

Sécurités :
- Decimal uniquement, jamais float pour le taux ni pour le calcul ;
- aucune troncature du taux ;
- aucune substitution silencieuse par le cours du jour ;
- si la page BAM ne permet pas de confirmer la date demandée, le taux est
  refusé et le document reste À VÉRIFIER ;
- cache PostgreSQL pour éviter des appels répétés à BAM.
"""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from html.parser import HTMLParser
from typing import Iterable
from urllib.parse import urlencode

import requests
from sqlalchemy.orm import Session

from app.models.taux_change_bam import TauxChangeBAM

logger = logging.getLogger("comptaflow.exchange_rate")

SOURCE_BAM_BILLETS = "bam_billets_etrangers"
BAM_FOREIGN_BANKNOTES_URL = (
    "https://www.bkam.ma/en/Markets/Key-indicators/Foreign-exchange-market/"
    "Foreign-exchange-rates/Foreign-banknotes-exchange-rate"
)
_TIMEOUT_SECONDS = 20

# La page officielle « billets étrangers » expose actuellement ces devises.
# Les alias servent uniquement à normaliser la donnée extraite du document.
_ALIASES_DEVISES: dict[str, str] = {
    "MAD": "MAD",
    "DH": "MAD",
    "DHS": "MAD",
    "DIRHAM": "MAD",
    "DIRHAMS": "MAD",
    "DIRHAM MAROCAIN": "MAD",
    "EUR": "EUR",
    "EURO": "EUR",
    "EUROS": "EUR",
    "€": "EUR",
    "USD": "USD",
    "US DOLLAR": "USD",
    "DOLLAR US": "USD",
    "DOLLAR USA": "USD",
    "DOLLAR U.S.A.": "USD",
    "$": "USD",
    "CAD": "CAD",
    "CANADIAN DOLLAR": "CAD",
    "DOLLAR CANADIEN": "CAD",
    "GBP": "GBP",
    "POUND STERLING": "GBP",
    "LIVRE STERLING": "GBP",
    "GIP": "GIP",
    "GIBRALTAR POUND": "GIP",
    "LIVRE GIBRALTAR": "GIP",
    "CHF": "CHF",
    "SWISS FRANC": "CHF",
    "FRANC SUISSE": "CHF",
    "SAR": "SAR",
    "SAUDI RIYAL": "SAR",
    "RIYAL SAOUDIEN": "SAR",
    "KWD": "KWD",
    "KUWAITI DINAR": "KWD",
    "DINAR KOWEITIEN": "KWD",
    "AED": "AED",
    "UAE DIRHAM": "AED",
    "DIRHAM E.A.U.": "AED",
    "QAR": "QAR",
    "QATARI RIYAL": "QAR",
    "RIYAL QATARI": "QAR",
    "BHD": "BHD",
    "BAHREINI DINAR": "BHD",
    "DINAR BAHREINI": "BHD",
    "JPY": "JPY",
    "JAPANESE YEN": "JPY",
    "YEN JAPONAIS": "JPY",
    "YENS JAPONAIS": "JPY",
    "OMR": "OMR",
    "OMANI RIAL": "OMR",
    "RIAL OMANI": "OMR",
}


class TauxChangeIndisponible(RuntimeError):
    """Le cours demandé n'a pas pu être obtenu de façon sûre."""


@dataclass(frozen=True)
class TauxChangeResultat:
    date_cours: date
    devise: str
    unite_cotation: int
    libelle_bam: str
    cours_achat: Decimal
    cours_vente: Decimal
    source: str
    source_url: str
    depuis_cache: bool


@dataclass(frozen=True)
class ConversionFactureResultat:
    donnees_comptables: dict
    raisons: tuple[str, ...]
    conversion_effectuee: bool


@dataclass(frozen=True)
class ConversionMouvementResultat:
    devise_originale: str
    montant_devise: Decimal
    montant_mad: Decimal | None
    taux_change: Decimal | None
    type_cours_change: str | None
    date_cours_change: date | None
    unite_cotation: int | None
    source_cours_change: str | None
    raison: str | None
    montant_mad_theorique: Decimal | None
    montant_mad_source: str


class _TableHTMLParser(HTMLParser):
    """Mini parseur standard-library : aucun nouveau package requis."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self._in_row = False
        self._in_cell = False
        self._current_cell: list[str] = []
        self._current_row: list[str] = []
        self.rows: list[list[str]] = []
        self.date_input_values: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        lowered = tag.lower()
        attr_map = {str(k).lower(): str(v or "") for k, v in attrs}

        if lowered == "input":
            name = attr_map.get("name", "").lower()
            element_id = attr_map.get("id", "").lower()
            if "date" in name or "date" in element_id:
                value = attr_map.get("value", "").strip()
                if value:
                    self.date_input_values.append(value)

        if lowered == "tr":
            self._in_row = True
            self._current_row = []
        elif lowered in {"td", "th"} and self._in_row:
            self._in_cell = True
            self._current_cell = []

    def handle_data(self, data: str) -> None:
        if self._in_cell:
            self._current_cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered in {"td", "th"} and self._in_cell:
            text = " ".join("".join(self._current_cell).split())
            self._current_row.append(text)
            self._current_cell = []
            self._in_cell = False
        elif lowered == "tr" and self._in_row:
            if self._current_row:
                self.rows.append(self._current_row)
            self._current_row = []
            self._in_row = False


def _sans_accents(value: str) -> str:
    return "".join(
        char
        for char in unicodedata.normalize("NFKD", value)
        if not unicodedata.combining(char)
    )


def _texte_normalise(value: object | None) -> str:
    if value is None:
        return ""
    text = _sans_accents(str(value)).upper().replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def normaliser_devise(value: object | None) -> str | None:
    """Normalise une devise extraite vers un code ISO court."""
    text = _texte_normalise(value)
    if not text:
        return None

    if text in _ALIASES_DEVISES:
        return _ALIASES_DEVISES[text]

    compact = re.sub(r"[^A-Z]", "", text)
    if len(compact) == 3 and compact in {
        "MAD", "EUR", "USD", "CAD", "GBP", "GIP", "CHF", "SAR",
        "KWD", "AED", "QAR", "BHD", "JPY", "OMR",
    }:
        return compact

    for alias, code in _ALIASES_DEVISES.items():
        if len(alias) >= 4 and _texte_normalise(alias) in text:
            return code

    return None


def _vers_decimal(value: object | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        # str(float) évite de récupérer l'approximation binaire complète.
        return Decimal(str(value))

    text = str(value).strip().replace("\u00a0", "").replace(" ", "")
    if not text:
        return None

    if "," in text and "." in text:
        # 1.234,56 -> 1234.56
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    text = re.sub(r"[^0-9+\-.]", "", text)
    if not text:
        return None

    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _identifier_devise_bam(libelle: str) -> str | None:
    normalized = _texte_normalise(libelle)
    # L'ordre évite que « DOLLAR » générique n'écrase CAD.
    rules = (
        ("CANADIAN DOLLAR", "CAD"),
        ("DOLLAR CANADIEN", "CAD"),
        ("US DOLLAR", "USD"),
        ("DOLLAR U.S.A", "USD"),
        ("DOLLAR USA", "USD"),
        ("GIBRALTAR POUND", "GIP"),
        ("LIVRE GIBRALTAR", "GIP"),
        ("POUND STERLING", "GBP"),
        ("LIVRE STERLING", "GBP"),
        ("SWISS FRANC", "CHF"),
        ("FRANC SUISSE", "CHF"),
        ("SAUDI RIYAL", "SAR"),
        ("RIYAL SAOUDIEN", "SAR"),
        ("KUWAITI DINAR", "KWD"),
        ("DINAR KOWEITIEN", "KWD"),
        ("UAE DIRHAM", "AED"),
        ("DIRHAM E.A.U", "AED"),
        ("QATARI RIYAL", "QAR"),
        ("RIYAL QATARI", "QAR"),
        ("BAHREINI DINAR", "BHD"),
        ("DINAR BAHREINI", "BHD"),
        ("JAPANESE YEN", "JPY"),
        ("YEN JAPONAIS", "JPY"),
        ("OMANI RIAL", "OMR"),
        ("RIAL OMANI", "OMR"),
        ("EURO", "EUR"),
    )
    for token, code in rules:
        if token in normalized:
            return code
    return None


def _extraire_unite_cotation(libelle: str) -> int:
    match = re.match(r"\s*(\d+)\b", libelle)
    if not match:
        return 1
    try:
        return max(1, int(match.group(1)))
    except ValueError:
        return 1


def _date_reponse_confirmee(html: str, parser: _TableHTMLParser, requested: date) -> bool:
    candidates = {
        requested.strftime("%d/%m/%Y"),
        requested.isoformat(),
        requested.strftime("%d-%m-%Y"),
    }
    values = {value.strip() for value in parser.date_input_values}
    if values.intersection(candidates):
        return True
    return any(candidate in html for candidate in candidates)


def _parser_page_bam(html: str, requested: date) -> list[dict]:
    parser = _TableHTMLParser()
    parser.feed(html)

    if not _date_reponse_confirmee(html, parser, requested):
        raise TauxChangeIndisponible(
            "Bank Al-Maghrib n'a pas confirmé la date demandée dans la réponse. "
            "Le taux est refusé pour éviter d'utiliser silencieusement un autre jour."
        )

    rows: list[dict] = []
    for cells in parser.rows:
        if len(cells) < 3:
            continue
        libelle = cells[0].strip()
        devise = _identifier_devise_bam(libelle)
        if devise is None:
            continue

        achat = _vers_decimal(cells[1])
        vente = _vers_decimal(cells[2])
        if achat is None or vente is None:
            continue

        rows.append(
            {
                "devise": devise,
                "libelle_bam": libelle,
                "unite_cotation": _extraire_unite_cotation(libelle),
                "cours_achat": achat,
                "cours_vente": vente,
            }
        )

    if not rows:
        raise TauxChangeIndisponible(
            "Aucun cours Achat/Vente exploitable n'a été trouvé dans la page BAM."
        )

    return rows


def _source_url(date_cours: date) -> str:
    return f"{BAM_FOREIGN_BANKNOTES_URL}?{urlencode({'date': date_cours.strftime('%d/%m/%Y')})}"


def _telecharger_page_bam(date_cours: date) -> tuple[str, str]:
    requested = date_cours.strftime("%d/%m/%Y")
    headers = {
        "User-Agent": "ComptaFlow/1.0 (+exchange-rate retrieval; official BAM source)",
        "Accept": "text/html,application/xhtml+xml",
        "Accept-Language": "en,fr;q=0.9",
    }
    try:
        response = requests.get(
            BAM_FOREIGN_BANKNOTES_URL,
            params={"date": requested},
            headers=headers,
            timeout=_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise TauxChangeIndisponible(
            f"Consultation Bank Al-Maghrib impossible : {exc}"
        ) from exc

    return response.text, response.url


def _enregistrer_rows_cache(
    db: Session,
    date_cours: date,
    rows: Iterable[dict],
    source_url: str,
) -> None:
    for row in rows:
        existing = (
            db.query(TauxChangeBAM)
            .filter(
                TauxChangeBAM.date_cours == date_cours,
                TauxChangeBAM.devise == row["devise"],
                TauxChangeBAM.source == SOURCE_BAM_BILLETS,
            )
            .first()
        )
        if existing is None:
            existing = TauxChangeBAM(
                date_cours=date_cours,
                devise=row["devise"],
                unite_cotation=row["unite_cotation"],
                libelle_bam=row["libelle_bam"],
                cours_achat=row["cours_achat"],
                cours_vente=row["cours_vente"],
                source=SOURCE_BAM_BILLETS,
                source_url=source_url,
            )
            db.add(existing)
        else:
            existing.unite_cotation = row["unite_cotation"]
            existing.libelle_bam = row["libelle_bam"]
            existing.cours_achat = row["cours_achat"]
            existing.cours_vente = row["cours_vente"]
            existing.source_url = source_url

    # flush seulement : le caller conserve la transaction atomique du pipeline.
    db.flush()


def obtenir_taux_bam(
    db: Session,
    date_cours: date,
    devise: object,
) -> TauxChangeResultat:
    code = normaliser_devise(devise)
    if code is None:
        raise TauxChangeIndisponible(f"Devise non reconnue : {devise!r}.")
    if code == "MAD":
        raise ValueError("MAD ne nécessite pas de consultation BAM.")

    cached = (
        db.query(TauxChangeBAM)
        .filter(
            TauxChangeBAM.date_cours == date_cours,
            TauxChangeBAM.devise == code,
            TauxChangeBAM.source == SOURCE_BAM_BILLETS,
        )
        .first()
    )
    if cached is not None:
        return TauxChangeResultat(
            date_cours=cached.date_cours,
            devise=cached.devise,
            unite_cotation=cached.unite_cotation,
            libelle_bam=cached.libelle_bam,
            cours_achat=Decimal(cached.cours_achat),
            cours_vente=Decimal(cached.cours_vente),
            source=cached.source,
            source_url=cached.source_url,
            depuis_cache=True,
        )

    html, final_url = _telecharger_page_bam(date_cours)
    rows = _parser_page_bam(html, date_cours)
    _enregistrer_rows_cache(db, date_cours, rows, final_url or _source_url(date_cours))

    row = next((item for item in rows if item["devise"] == code), None)
    if row is None:
        raise TauxChangeIndisponible(
            f"La devise {code} n'est pas disponible dans le tableau BAM du {date_cours.isoformat()}."
        )

    return TauxChangeResultat(
        date_cours=date_cours,
        devise=code,
        unite_cotation=int(row["unite_cotation"]),
        libelle_bam=str(row["libelle_bam"]),
        cours_achat=Decimal(row["cours_achat"]),
        cours_vente=Decimal(row["cours_vente"]),
        source=SOURCE_BAM_BILLETS,
        source_url=final_url or _source_url(date_cours),
        depuis_cache=False,
    )


def convertir_montant_mad(
    montant_devise: Decimal,
    taux: Decimal,
    unite_cotation: int,
) -> Decimal:
    if unite_cotation <= 0:
        raise ValueError("unite_cotation doit être strictement positive.")
    result = montant_devise * taux / Decimal(unite_cotation)
    return result.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _append_reason(donnees: dict, message: str) -> None:
    previous = str(donnees.get("raison_verification") or "").strip()
    if previous and message not in previous:
        donnees["raison_verification"] = f"{previous} | {message}"
    elif not previous:
        donnees["raison_verification"] = message
    donnees["a_verifier"] = True


def _parse_date(value: object | None) -> date | None:
    if isinstance(value, date):
        return value
    if value is None:
        return None
    try:
        return date.fromisoformat(str(value).strip())
    except ValueError:
        return None


def preparer_facture_pour_comptabilite(
    db: Session,
    donnees: dict,
    *,
    type_ecriture: str,
) -> ConversionFactureResultat:
    """Prépare une copie MAD sans écraser les montants originaux du document."""
    original = donnees
    pour_compta = dict(donnees)
    devise = normaliser_devise(donnees.get("devise"))

    if devise in {None, "MAD"}:
        original["conversion_devise_statut"] = "non_requise"
        original["devise_originale"] = devise or "MAD"
        return ConversionFactureResultat(pour_compta, (), False)

    original["devise_originale"] = devise
    original["source_cours_change"] = SOURCE_BAM_BILLETS

    date_piece = _parse_date(donnees.get("date_piece"))
    if date_piece is None:
        message = (
            f"Facture en {devise} : date de pièce absente/invalide, "
            "cours BAM impossible à déterminer."
        )
        _append_reason(original, message)
        original["conversion_devise_statut"] = "date_manquante"
        for key in ("montant_ht", "montant_tva", "montant_ttc", "montant_document"):
            pour_compta[key] = None
        return ConversionFactureResultat(pour_compta, (message,), False)

    normalized_type = str(type_ecriture).strip().lower()
    if normalized_type == "achat":
        type_cours = "vente_clientele"
    elif normalized_type == "vente":
        type_cours = "achat_clientele"
    else:
        message = (
            f"Document en {devise} : sens Achat/Vente non déterminé, "
            "conversion BAM automatique refusée."
        )
        _append_reason(original, message)
        original["conversion_devise_statut"] = "sens_indetermine"
        for key in ("montant_ht", "montant_tva", "montant_ttc", "montant_document"):
            pour_compta[key] = None
        return ConversionFactureResultat(pour_compta, (message,), False)

    try:
        rate = obtenir_taux_bam(db, date_piece, devise)
    except (TauxChangeIndisponible, requests.RequestException) as exc:
        message = f"Facture en {devise} : cours BAM indisponible pour {date_piece.isoformat()} ({exc})."
        _append_reason(original, message)
        original["conversion_devise_statut"] = "cours_introuvable"
        original["date_cours_change"] = date_piece.isoformat()
        original["type_cours_change"] = type_cours
        for key in ("montant_ht", "montant_tva", "montant_ttc", "montant_document"):
            pour_compta[key] = None
        return ConversionFactureResultat(pour_compta, (message,), False)

    taux = rate.cours_vente if type_cours == "vente_clientele" else rate.cours_achat

    original["conversion_devise_statut"] = "convertie"
    original["date_cours_change"] = rate.date_cours.isoformat()
    original["type_cours_change"] = type_cours
    original["taux_change"] = format(taux, "f")
    original["unite_cotation"] = rate.unite_cotation
    original["source_cours_change"] = rate.source
    original["source_url_cours_change"] = rate.source_url
    original["taux_depuis_cache"] = rate.depuis_cache

    for key in ("montant_ht", "montant_tva", "montant_ttc", "montant_document"):
        amount = _vers_decimal(donnees.get(key))
        if amount is None:
            continue
        original[f"{key}_devise"] = format(amount, "f")
        mad = convertir_montant_mad(amount, taux, rate.unite_cotation)
        original[f"{key}_mad"] = format(mad, "f")
        pour_compta[key] = mad

    return ConversionFactureResultat(pour_compta, (), True)


def convertir_mouvement_bancaire(
    db: Session,
    *,
    date_operation: date,
    devise: object | None,
    type_mouvement: str,
    montant: Decimal,
    montant_mad_reel: Decimal | None = None,
) -> ConversionMouvementResultat:
    code = normaliser_devise(devise) or "MAD"
    if code == "MAD":
        return ConversionMouvementResultat(
            devise_originale="MAD",
            montant_devise=montant,
            montant_mad=montant.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            taux_change=None,
            type_cours_change=None,
            date_cours_change=None,
            unite_cotation=1,
            source_cours_change=None,
            raison=None,
            montant_mad_theorique=montant.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP),
            montant_mad_source="mad",
        )

    movement_type = str(type_mouvement).strip().lower()
    if movement_type == "debit":
        type_cours = "vente_clientele"
    elif movement_type == "credit":
        type_cours = "achat_clientele"
    else:
        return ConversionMouvementResultat(
            devise_originale=code,
            montant_devise=montant,
            montant_mad=None,
            taux_change=None,
            type_cours_change=None,
            date_cours_change=date_operation,
            unite_cotation=None,
            source_cours_change=SOURCE_BAM_BILLETS,
            raison="Sens débit/crédit indéterminé : conversion devise refusée.",
            montant_mad_theorique=None,
            montant_mad_source="indisponible",
        )

    try:
        rate = obtenir_taux_bam(db, date_operation, code)
    except TauxChangeIndisponible as exc:
        actual = (
            montant_mad_reel.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            if montant_mad_reel is not None
            else None
        )
        return ConversionMouvementResultat(
            devise_originale=code,
            montant_devise=montant,
            montant_mad=actual,
            taux_change=None,
            type_cours_change=type_cours,
            date_cours_change=date_operation,
            unite_cotation=None,
            source_cours_change=SOURCE_BAM_BILLETS,
            raison=f"Cours BAM indisponible pour {date_operation.isoformat()} : {exc}",
            montant_mad_theorique=None,
            montant_mad_source="banque" if actual is not None else "indisponible",
        )

    taux = rate.cours_vente if type_cours == "vente_clientele" else rate.cours_achat
    mad_theorique = convertir_montant_mad(montant, taux, rate.unite_cotation)
    actual = (
        montant_mad_reel.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        if montant_mad_reel is not None
        else mad_theorique
    )
    return ConversionMouvementResultat(
        devise_originale=code,
        montant_devise=montant,
        montant_mad=actual,
        taux_change=taux,
        type_cours_change=type_cours,
        date_cours_change=rate.date_cours,
        unite_cotation=rate.unite_cotation,
        source_cours_change=rate.source,
        raison=None,
        montant_mad_theorique=mad_theorique,
        montant_mad_source="banque" if montant_mad_reel is not None else "bam",
    )
