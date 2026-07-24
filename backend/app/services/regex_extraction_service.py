"""
app/services/regex_extraction_service.py

Extraction des champs numériques/identifiants par regex -- méthode
PRINCIPALE pour tout ce qui suit un format fixe (ICE, IF, RC, dates,
numéro de pièce, montants HT/TVA/TTC, taux de TVA).

Consolidé Sprint 3 + 4 :
- Pré-normalisation du texte OCR (aplatissement des sauts de ligne
  pour que "Montant TTC" et sa valeur, coupés par un retour à la
  ligne, se retrouvent sur la même ligne logique).
- Tolérance aux erreurs OCR classiques (O/I/L <-> 0/1, espaces
  parasites dans les montants et les identifiants).
- Score de confiance (0.0 à 1.0) par champ, dans
  donnees["confiance_par_champ"].
"""
import re

# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

_PATTERN_ICE = re.compile(r"(?:ICE|1CE|lCE|I\.C\.E)\s*[:\-]?\s*([0-9OoIl]{15})", re.IGNORECASE)
_PATTERN_ICE_BRUT = re.compile(r"\b([0-9OoIl]{15})\b")

_PATTERN_IF = re.compile(
    r"(?:I\.?F\.?|1\.?F\.?|Identifiant\s+Fiscal)\s*[:\-]?\s*([0-9Oo]{6,8})",
    re.IGNORECASE,
)

_PATTERN_RC = re.compile(
    r"(?:R\.?C\.?|Registre\s+de\s+Commerce)\s*(?:N°|N|No|:)?\s*[:\-]?\s*([0-9Oo]{3,8})",
    re.IGNORECASE,
)

_PATTERN_PATENTE = re.compile(r"Patente\s*[:\-]?\s*([0-9Oo]{6,10})", re.IGNORECASE)

# Tolère les slash lus comme des "1" ou des "l" par l'OCR.
_PATTERN_DATE = re.compile(r"\b(\d{1,2})\s*[/\-.\|l]\s*(\d{1,2})\s*[/\-.\|l]\s*(\d{4})\b")

_PATTERN_NUMERO_PIECE = re.compile(
    r"\b(?:Facture|Fact\.?|N°|No\.?|Num(?:éro)?)\b\s*[:\-]?\s*"
    r"([A-Z0-9][A-Z0-9\-/]{2,20})",
    re.IGNORECASE,
)
_PATTERN_NUMERO_PIECE_HASH = re.compile(r"#\s*([A-Z0-9\-/]{2,20})", re.IGNORECASE)

# Tolère un nombre variable d'espaces entre les chiffres (OCR qui
# "éclate" un montant : "1 2 3 4 , 5 0").
_MONTANT_NUM = r"((?:\d\s*){1,10}(?:[.,]\s*\d{1,2})?)"

_PATTERN_MONTANT_HT = re.compile(
    r"(?:Total\s*HT|Montant\s*HT|H\.T\.?)\s*[:\-]?\s*" + _MONTANT_NUM, re.IGNORECASE
)

_PATTERN_MONTANT_TTC = re.compile(
    r"(?:TOTAL\s+GENERAL|Total\s+g[ée]n[ée]ral|Total\s*TTC|Montant\s*TTC|"
    r"Net\s*[àa]\s*payer|(?<!sous\s)(?<!sous-)\bTOTAL\b|TTC)\s*[:\-]?\s*"
    + _MONTANT_NUM,
    re.IGNORECASE,
)

_PATTERN_MONTANT_TVA = re.compile(
    r"(?:Montant\s*TVA|TVA)\s*(?:\(\s*\d{1,2}(?:[.,]\d+)?\s*%\s*\))?\s*[:\-]?\s*"
    + _MONTANT_NUM,
    re.IGNORECASE,
)

_PATTERN_TAUX_TVA = re.compile(
    r"TVA\s*(?:\()?\s*(\d{1,2})\s*(?:[.,]\s*\d+)?\s*%\s*(?:\))?", re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Normalisation
# ---------------------------------------------------------------------------

def _pre_normaliser_texte(texte_ocr: str) -> str:
    if not texte_ocr:
        return ""
    texte = re.sub(r"\n+", " \n ", texte_ocr)
    texte = re.sub(r"[ \t]+", " ", texte)
    return texte


def _normaliser_chiffres(valeur_brute: str) -> str | None:
    """Corrige les confusions OCR fréquentes sur des identifiants."""
    if not valeur_brute:
        return None
    v = valeur_brute.upper().replace(" ", "")
    v = v.replace("O", "0").replace("I", "1").replace("L", "1")
    return v


def _normaliser_montant(valeur_brute: str) -> float | None:
    if not valeur_brute:
        return None
    nettoye = (
        valeur_brute.strip()
        .replace(" ", "")
        .replace("\xa0", "")
        .replace("O", "0")
        .replace("o", "0")
    )
    if "," in nettoye and "." in nettoye:
        if nettoye.rfind(",") > nettoye.rfind("."):
            nettoye = nettoye.replace(".", "").replace(",", ".")
        else:
            nettoye = nettoye.replace(",", "")
    elif "," in nettoye:
        nettoye = nettoye.replace(",", ".")
    try:
        return round(float(nettoye), 2)
    except ValueError:
        return None


def _extraire(pattern: re.Pattern, texte: str, score: float, is_amount=False, is_id=False):
    match = pattern.search(texte)
    if not match:
        return None, 0.0
    brut = match.group(1)
    if is_amount:
        return _normaliser_montant(brut), score
    if is_id:
        return _normaliser_chiffres(brut), score
    return brut.strip(), score


# ---------------------------------------------------------------------------
# Fonctions principales
# ---------------------------------------------------------------------------

def completer_champs_manquants(donnees: dict, texte_ocr: str) -> dict:
    """Complète tous les champs encore à None + remplit
    donnees["confiance_par_champ"]. Ne JAMAIS écraser un champ déjà rempli."""
    if not texte_ocr:
        return donnees

    texte = _pre_normaliser_texte(texte_ocr)
    conf = donnees.setdefault("confiance_par_champ", {})

    if donnees.get("ice") is None:
        val, score = _extraire(_PATTERN_ICE, texte, 0.95, is_id=True)
        if not val:
            val, score = _extraire(_PATTERN_ICE_BRUT, texte, 0.55, is_id=True)
        donnees["ice"], conf["ice"] = val, score

    if donnees.get("identifiant_fiscal") is None:
        val, score = _extraire(_PATTERN_IF, texte, 0.90, is_id=True)
        donnees["identifiant_fiscal"], conf["identifiant_fiscal"] = val, score

    if donnees.get("rc") is None:
        val, score = _extraire(_PATTERN_RC, texte, 0.90, is_id=True)
        donnees["rc"], conf["rc"] = val, score

    if donnees.get("date_piece") is None:
        m = _PATTERN_DATE.search(texte)
        if m:
            jour, mois, annee = m.groups()
            donnees["date_piece"] = f"{annee}-{mois.zfill(2)}-{jour.zfill(2)}"
            conf["date_piece"] = 0.85
        else:
            conf["date_piece"] = 0.0

    if donnees.get("numero_piece") is None:
        val, score = _extraire(_PATTERN_NUMERO_PIECE, texte, 0.90)
        if not val:
            val, score = _extraire(_PATTERN_NUMERO_PIECE_HASH, texte, 0.80)
        donnees["numero_piece"], conf["numero_piece"] = val, score

    if donnees.get("montant_ht") is None:
        val, score = _extraire(_PATTERN_MONTANT_HT, texte, 0.90, is_amount=True)
        donnees["montant_ht"], conf["montant_ht"] = val, score

    if donnees.get("taux_tva") is None:
        val, score = _extraire(_PATTERN_TAUX_TVA, texte, 0.85, is_amount=True)
        donnees["taux_tva"], conf["taux_tva"] = val, score

    if donnees.get("montant_tva") is None:
        val, score = _extraire(_PATTERN_MONTANT_TVA, texte, 0.90, is_amount=True)
        donnees["montant_tva"], conf["montant_tva"] = val, score

    if donnees.get("montant_ttc") is None:
        val, score = _extraire(_PATTERN_MONTANT_TTC, texte, 0.95, is_amount=True)
        donnees["montant_ttc"], conf["montant_ttc"] = val, score

    return donnees


def verifier_coherence_montants(donnees: dict) -> dict:
    """Garde-fou : si HT + TVA == TTC (tolérance 1 Dh), confiance -> 1.0
    sur les 3 montants. Sinon, confiance divisée par 2 et a_verifier=True."""
    donnees["a_verifier"] = False
    donnees["raison_verification"] = None
    conf = donnees.setdefault("confiance_par_champ", {})

    ht = donnees.get("montant_ht")
    tva = donnees.get("montant_tva")
    ttc = donnees.get("montant_ttc")

    if ht is not None and tva is not None and ttc is not None:
        try:
            ht_f, tva_f, ttc_f = float(ht), float(tva), float(ttc)
            if abs((ht_f + tva_f) - ttc_f) <= 1.0:
                conf["montant_ht"] = conf["montant_tva"] = conf["montant_ttc"] = 1.0
            else:
                donnees["a_verifier"] = True
                donnees["raison_verification"] = (
                    f"Incohérence montants: HT({ht_f}) + TVA({tva_f}) "
                    f"= {ht_f + tva_f} != TTC({ttc_f})"
                )
                for champ in ("montant_ht", "montant_tva", "montant_ttc"):
                    conf[champ] = conf.get(champ, 0.9) * 0.5
        except (ValueError, TypeError):
            donnees["a_verifier"] = True
            donnees["raison_verification"] = "Montants non numériques détectés"

    return donnees