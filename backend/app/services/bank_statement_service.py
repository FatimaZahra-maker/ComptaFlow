"""Extraction dédiée des relevés bancaires.

Ce service est volontairement isolé du traitement des factures. Il n'altère ni
les prompts facture existants, ni Ollama, ni PaddleOCR. Il intervient seulement
quand le document est reconnu comme un relevé bancaire.

Objectifs :
- extraire toutes les pages d'un relevé ;
- conserver chaque ligne de transaction, même incomplète ou répétée ;
- normaliser dates, débits, crédits et montants ;
- contrôler les totaux et les soldes imprimés ;
- marquer clairement les éléments à vérifier au lieu de les supprimer.
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from datetime import date, datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Any, Iterable

import requests

from app.core.config import settings

logger = logging.getLogger("comptaflow.bank_statement_service")

_GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
_VISION_MODEL = "qwen/qwen3.6-27b"
_TIMEOUT_SECONDS = 60
_NOMBRE_TENTATIVES = 2
_DELAI_RETRY_SECONDS = 1.5
_MAX_TOKENS_PAGE = 8192
_MAX_CHARS_CHUNK_TEXTE = 9000
_TOLERANCE_MAD = Decimal("0.05")

_SCHEMA_PAGE = r"""{
  "type_document": "releve_bancaire",
  "banque": string | null,
  "titulaire_compte": string | null,
  "rib": string | null,
  "periode_debut": "YYYY-MM-DD" | null,
  "periode_fin": "YYYY-MM-DD" | null,
  "solde_depart": number | null,
  "solde_final": number | null,
  "total_debit_imprime": number | null,
  "total_credit_imprime": number | null,
  "nombre_lignes_detectees": integer | null,
  "lignes_bancaires": [
    {
      "code_operation": string | null,
      "date_operation": "YYYY-MM-DD" | null,
      "date_valeur": "YYYY-MM-DD" | null,
      "libelle_original": string | null,
      "reference": string | null,
      "debit": number | null,
      "credit": number | null,
      "solde_apres_operation": number | null,
      "texte_brut": string | null
    }
  ]
}"""

_PROMPT_IMAGE = """Tu es spécialiste des relevés bancaires marocains.
Analyse UNE PAGE de relevé bancaire et retourne uniquement un objet JSON valide.

RÈGLE ABSOLUE : conserve CHAQUE ligne de transaction imprimée dans le tableau,
dans son ordre visuel. Ne regroupe jamais deux lignes, ne supprime jamais une
ligne répétée et n'invente aucune opération. Une ligne partiellement illisible
doit quand même être renvoyée avec les champs lisibles, les autres à null, et
son texte dans texte_brut.

Pour chaque opération :
- code_operation : code bancaire situé au début de la ligne, s'il existe ;
- date_operation et date_valeur : format YYYY-MM-DD. Si l'année n'est pas
  répétée sur chaque ligne, déduis-la uniquement de la période imprimée ;
- libelle_original : libellé imprimé complet, sans reformulation ;
- reference : référence, numéro de chèque, LCN, prélèvement ou virement ;
- debit : montant de la colonne débit/retrait/décaissement ;
- credit : montant de la colonne crédit/dépôt/encaissement ;
- une opération doit avoir au maximum un débit ou un crédit ;
- texte_brut : transcription fidèle de la ligne entière.

N'ajoute pas dans lignes_bancaires les en-têtes, soldes initiaux, sous-totaux,
totaux ou soldes finaux. Ils doivent être placés dans les champs généraux.
Ignore uniquement les annotations manuscrites et tampons ajoutés après coup.

Schéma exact :
""" + _SCHEMA_PAGE

_PROMPT_TEXTE = """Tu es spécialiste des relevés bancaires marocains.
Le texte ci-dessous provient de l'OCR d'une partie de relevé bancaire.
Retourne uniquement un objet JSON valide selon le schéma fourni.

RÈGLE ABSOLUE : renvoie CHAQUE ligne de transaction présente dans le texte,
dans le même ordre. Ne fusionne pas, ne déduplique pas et ne supprime pas les
lignes incomplètes. Pour une ligne incomplète, conserve texte_brut et mets les
champs non lisibles à null.

Débit = retrait/décaissement. Crédit = dépôt/encaissement.
Les en-têtes, soldes et totaux ne sont pas des transactions.

Schéma exact :
""" + _SCHEMA_PAGE + """

Texte OCR :
---
{texte}
---
"""


def _decimal_ou_none(value: Any) -> Decimal | None:
    """Convertit les formats français et internationaux en Decimal."""
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    text = str(value).strip()
    if not text:
        return None

    text = (
        text.replace("MAD", "")
        .replace("DH", "")
        .replace("DHS", "")
        .replace("\u00a0", " ")
        .replace("'", "")
        .strip()
    )
    text = re.sub(r"\s+", "", text)

    # 1.234,56 -> 1234.56 ; 1,234.56 -> 1234.56 ; 1234,56 -> 1234.56
    if "," in text and "." in text:
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        text = text.replace(",", ".")

    text = re.sub(r"[^0-9.\-]", "", text)
    if text in {"", "-", ".", "-."}:
        return None

    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None


def _float_ou_none(value: Any) -> float | None:
    decimal_value = _decimal_ou_none(value)
    return float(decimal_value) if decimal_value is not None else None


def _normaliser_date(value: Any, annee_reference: int | None = None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()

    text = str(value).strip()
    if not text:
        return None

    # Nettoie les espaces autour des séparateurs.
    text = re.sub(r"\s*[/.-]\s*", "/", text)

    formats = (
        "%Y/%m/%d",
        "%d/%m/%Y",
        "%d/%m/%y",
    )
    for fmt in formats:
        try:
            return datetime.strptime(text, fmt).date().isoformat()
        except ValueError:
            pass

    # Les relevés affichent souvent seulement JJ/MM pour chaque ligne.
    match = re.fullmatch(r"(\d{1,2})/(\d{1,2})", text)
    if match and annee_reference is not None:
        day, month = int(match.group(1)), int(match.group(2))
        try:
            return date(annee_reference, month, day).isoformat()
        except ValueError:
            return None

    return None


def _annee_depuis_periode(*values: Any) -> int | None:
    for value in values:
        normalized = _normaliser_date(value)
        if normalized:
            return int(normalized[:4])
    return None


def _texte_ou_none(value: Any, max_length: int | None = None) -> str | None:
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    if not text:
        return None
    return text[:max_length] if max_length else text


def _parser_json(response_text: str | None) -> dict[str, Any] | None:
    if not response_text:
        return None
    cleaned = response_text.replace("```json", "").replace("```", "").strip()
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        parsed = json.loads(cleaned[start : end + 1])
    except json.JSONDecodeError:
        return None
    return parsed if isinstance(parsed, dict) else None


def _is_transient(error: Exception) -> bool:
    if isinstance(error, (requests.exceptions.Timeout, requests.exceptions.ConnectionError)):
        return True
    return (
        isinstance(error, requests.exceptions.HTTPError)
        and error.response is not None
        and error.response.status_code >= 500
    )


def _groq_request(payload: dict[str, Any]) -> dict[str, Any] | None:
    headers = {
        "Authorization": f"Bearer {settings.GROQ_API_KEY}",
        "Content-Type": "application/json",
    }

    for attempt in range(1, _NOMBRE_TENTATIVES + 1):
        try:
            response = requests.post(
                _GROQ_URL,
                headers=headers,
                json=payload,
                timeout=_TIMEOUT_SECONDS,
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            parsed = _parser_json(content)
            if parsed is None:
                logger.warning("Groq Banque : réponse JSON invalide.")
            return parsed
        except (requests.exceptions.RequestException, KeyError, IndexError, TypeError) as error:
            response_body = ""
            if isinstance(error, requests.exceptions.HTTPError) and error.response is not None:
                response_body = f" | Réponse: {error.response.text[:500]}"

            if _is_transient(error) and attempt < _NOMBRE_TENTATIVES:
                logger.warning(
                    "Groq Banque : tentative %s/%s échouée, nouvel essai : %s%s",
                    attempt,
                    _NOMBRE_TENTATIVES,
                    error,
                    response_body,
                )
                time.sleep(_DELAI_RETRY_SECONDS)
                continue

            logger.warning(
                "Groq Banque : échec définitif tentative %s/%s : %s%s",
                attempt,
                _NOMBRE_TENTATIVES,
                error,
                response_body,
            )
            return None

    return None


def _encode_image(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode("ascii")


def extraire_page_depuis_image(path: str, page_number: int) -> dict[str, Any] | None:
    """Extrait toutes les transactions visibles sur une page image."""
    if not settings.GROQ_API_KEY:
        return None

    try:
        image_base64 = _encode_image(path)
    except OSError as error:
        logger.warning("Lecture page bancaire impossible : %s", error)
        return None

    payload = {
        "model": _VISION_MODEL,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": _PROMPT_IMAGE},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:image/png;base64,{image_base64}"},
                    },
                ],
            }
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_completion_tokens": _MAX_TOKENS_PAGE,
    }
    result = _groq_request(payload)
    if result is not None:
        result["page"] = page_number
    return result


def _split_text_preserving_lines(text: str, max_chars: int) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_size = 0

    for line in text.splitlines():
        line_size = len(line) + 1
        if current and current_size + line_size > max_chars:
            chunks.append("\n".join(current))
            current = []
            current_size = 0
        current.append(line)
        current_size += line_size

    if current:
        chunks.append("\n".join(current))

    return chunks or [text]


def extraire_releve_depuis_texte(text: str) -> dict[str, Any] | None:
    """Repli texte : traite l'OCR complet par morceaux sans couper les lignes."""
    if not settings.GROQ_API_KEY or not text.strip():
        return None

    pages: list[dict[str, Any]] = []
    for index, chunk in enumerate(
        _split_text_preserving_lines(text, _MAX_CHARS_CHUNK_TEXTE),
        start=1,
    ):
        payload = {
            "model": settings.GROQ_MODEL,
            "messages": [
                {
                    "role": "user",
                    "content": _PROMPT_TEXTE.replace("{texte}", chunk),
                }
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0,
            "max_tokens": _MAX_TOKENS_PAGE,
        }
        page_result = _groq_request(payload)
        if page_result is not None:
            page_result["page"] = index
            pages.append(page_result)

    if not pages:
        return None
    return normaliser_et_valider_releve(pages, source="groq_texte_banque")


def _first_non_empty(pages: Iterable[dict[str, Any]], key: str) -> Any:
    for page in pages:
        value = page.get(key)
        if value not in (None, "", []):
            return value
    return None


def _last_non_empty(pages: Iterable[dict[str, Any]], key: str) -> Any:
    for page in reversed(list(pages)):
        value = page.get(key)
        if value not in (None, "", []):
            return value
    return None


def _append_reason(reasons: list[str], reason: str) -> None:
    if reason and reason not in reasons:
        reasons.append(reason)


def _normalize_line(
    raw_line: Any,
    page_number: int,
    order: int,
    year_reference: int | None,
) -> dict[str, Any]:
    line = raw_line if isinstance(raw_line, dict) else {"texte_brut": str(raw_line)}

    debit = _float_ou_none(line.get("debit"))
    credit = _float_ou_none(line.get("credit"))
    reasons: list[str] = []

    if debit is not None and debit < 0:
        debit = abs(debit)
    if credit is not None and credit < 0:
        credit = abs(credit)

    if debit is not None and credit is not None:
        _append_reason(reasons, "La ligne contient simultanément un débit et un crédit.")

    if credit is not None and debit is None:
        movement_type = "CREDIT"
        amount = credit
    elif debit is not None and credit is None:
        movement_type = "DEBIT"
        amount = debit
    elif credit is not None and debit is not None:
        # On conserve les deux colonnes. Le montant technique choisit la valeur non nulle
        # la plus grande, mais la ligne reste obligatoirement à vérifier.
        movement_type = "CREDIT" if credit >= debit else "DEBIT"
        amount = max(credit, debit)
    else:
        movement_type = None
        amount = None
        _append_reason(reasons, "Montant débit/crédit non détecté.")

    operation_date = _normaliser_date(line.get("date_operation"), year_reference)
    value_date = _normaliser_date(line.get("date_valeur"), year_reference)
    if operation_date is None:
        _append_reason(reasons, "Date d'opération non détectée.")

    original_label = _texte_ou_none(
        line.get("libelle_original") or line.get("libelle"),
        500,
    )
    raw_text = _texte_ou_none(line.get("texte_brut"), 2000)
    if original_label is None:
        original_label = raw_text
    if original_label is None:
        original_label = "Ligne bancaire illisible"
        _append_reason(reasons, "Libellé non détecté.")

    completeness = 1.0
    if operation_date is None:
        completeness -= 0.25
    if amount is None:
        completeness -= 0.35
    if movement_type is None:
        completeness -= 0.20
    if original_label == "Ligne bancaire illisible":
        completeness -= 0.20

    return {
        "ordre": order,
        "page": page_number,
        "code_operation": _texte_ou_none(line.get("code_operation"), 100),
        "date_operation": operation_date,
        "date_valeur": value_date,
        "libelle_original": original_label,
        # Compatibilité avec le modèle existant.
        "libelle": original_label,
        "reference": _texte_ou_none(line.get("reference"), 100),
        "debit": debit,
        "credit": credit,
        "type_mouvement": movement_type,
        "montant": amount,
        "solde_apres_operation": _float_ou_none(line.get("solde_apres_operation")),
        "texte_brut": raw_text or original_label,
        "confiance": round(max(0.0, min(1.0, completeness)), 2),
        "a_verifier": bool(reasons),
        "raison_verification": " | ".join(reasons) if reasons else None,
    }


def normaliser_et_valider_releve(
    page_results: list[dict[str, Any]],
    source: str = "groq_vision_banque",
) -> dict[str, Any]:
    """Fusionne les pages sans dédupliquer les opérations et contrôle les totaux."""
    pages = [page for page in page_results if isinstance(page, dict)]

    period_start = _normaliser_date(_first_non_empty(pages, "periode_debut"))
    period_end = _normaliser_date(_last_non_empty(pages, "periode_fin"))
    year_reference = _annee_depuis_periode(period_start, period_end)

    lines: list[dict[str, Any]] = []
    announced_count = 0
    for page_index, page in enumerate(pages, start=1):
        page_number = int(page.get("page") or page_index)
        raw_lines = page.get("lignes_bancaires")
        if not isinstance(raw_lines, list):
            raw_lines = []

        try:
            announced_count += int(page.get("nombre_lignes_detectees") or len(raw_lines))
        except (TypeError, ValueError):
            announced_count += len(raw_lines)

        for raw_line in raw_lines:
            # Aucune déduplication : deux lignes identiques imprimées restent deux lignes.
            lines.append(
                _normalize_line(
                    raw_line,
                    page_number=page_number,
                    order=len(lines) + 1,
                    year_reference=year_reference,
                )
            )

    total_debit = sum(
        (_decimal_ou_none(line.get("debit")) or Decimal("0.00") for line in lines),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))
    total_credit = sum(
        (_decimal_ou_none(line.get("credit")) or Decimal("0.00") for line in lines),
        Decimal("0.00"),
    ).quantize(Decimal("0.01"))

    printed_debit = _decimal_ou_none(_last_non_empty(pages, "total_debit_imprime"))
    printed_credit = _decimal_ou_none(_last_non_empty(pages, "total_credit_imprime"))
    opening_balance = _decimal_ou_none(_first_non_empty(pages, "solde_depart"))
    closing_balance = _decimal_ou_none(_last_non_empty(pages, "solde_final"))

    verification_reasons: list[str] = []
    if not lines:
        _append_reason(verification_reasons, "Aucune ligne bancaire n'a été extraite.")
    if any(line["a_verifier"] for line in lines):
        _append_reason(verification_reasons, "Une ou plusieurs lignes sont incomplètes.")
    if announced_count and announced_count != len(lines):
        _append_reason(
            verification_reasons,
            f"L'IA annonce {announced_count} ligne(s), mais {len(lines)} ont été conservées.",
        )
    if printed_debit is not None and abs(printed_debit - total_debit) > _TOLERANCE_MAD:
        _append_reason(
            verification_reasons,
            f"Total débit extrait {total_debit} différent du total imprimé {printed_debit}.",
        )
    if printed_credit is not None and abs(printed_credit - total_credit) > _TOLERANCE_MAD:
        _append_reason(
            verification_reasons,
            f"Total crédit extrait {total_credit} différent du total imprimé {printed_credit}.",
        )

    calculated_closing: Decimal | None = None
    if opening_balance is not None:
        calculated_closing = (opening_balance + total_credit - total_debit).quantize(Decimal("0.01"))
        if closing_balance is not None and abs(calculated_closing - closing_balance) > _TOLERANCE_MAD:
            _append_reason(
                verification_reasons,
                f"Solde calculé {calculated_closing} différent du solde final imprimé {closing_balance}.",
            )

    needs_review = bool(verification_reasons)
    date_piece = period_end or period_start

    return {
        "type_document": "releve_bancaire",
        "categorie": "banque",
        "categorie_document": "releve_bancaire",
        "nom_entreprise": _first_non_empty(pages, "titulaire_compte"),
        "tiers": None,
        "banque": _first_non_empty(pages, "banque"),
        "titulaire_compte": _first_non_empty(pages, "titulaire_compte"),
        "rib": _first_non_empty(pages, "rib"),
        "periode_debut": period_start,
        "periode_fin": period_end,
        # Compatibilité avec le classement Chronos existant.
        "date_piece": date_piece,
        "solde_depart": float(opening_balance) if opening_balance is not None else None,
        "solde_final": float(closing_balance) if closing_balance is not None else None,
        "solde_final_calcule": float(calculated_closing) if calculated_closing is not None else None,
        "total_debit_imprime": float(printed_debit) if printed_debit is not None else None,
        "total_credit_imprime": float(printed_credit) if printed_credit is not None else None,
        "total_debit_calcule": float(total_debit),
        "total_credit_calcule": float(total_credit),
        "nombre_lignes_detectees": announced_count or len(lines),
        "nombre_lignes_extraites": len(lines),
        "extraction_bancaire_statut": "a_verifier" if needs_review else "valide",
        "a_verifier": needs_review,
        "raison_verification": " | ".join(verification_reasons) if verification_reasons else None,
        "source_extraction": source,
        "lignes_bancaires": lines,
        # Les montants de facture ne doivent jamais être remplis pour un relevé.
        "montant_ht": None,
        "taux_tva": None,
        "montant_tva": None,
        "montant_ttc": None,
    }
