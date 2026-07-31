"""
app/services/accounting_service.py

Ce service s'occupe de transformer les données extraites d'un Document (MVC2) 
en une écriture comptable structurée (EcritureComptable) ou en mouvements bancaires.
Il est orchestré par document_processing.py après le classement du document.

Résolution des montants manquants :
- Si seul montant_ttc est connu avec un taux de TVA, on calcule le HT et la TVA par déduction.
- Si aucun montant n'est exploitable, la valeur 0.00 est stockée en base (colonne NOT NULL) 
  et l'écriture est marquée avec une anomalie explicite pour forcer la vérification humaine.
"""
import uuid
import unicodedata
from datetime import date as date_type
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy.orm import Session

from app.models.document import Document
from app.models.ecriture import EcritureComptable
from app.models.mouvement_bancaire import MouvementBancaire
from app.models.enums import TypeEcritureEnum, TauxTVAEnum, StatutValidationEnum

# Mapping pour lier les catégories extraites par l'IA aux types d'écritures officiels
_MAPPING_CATEGORIE_TYPE = {
    "achats": TypeEcritureEnum.ACHAT,
    "fournisseurs": TypeEcritureEnum.ACHAT,
    "ventes": TypeEcritureEnum.VENTE,
    "clients": TypeEcritureEnum.VENTE,
    "banque": TypeEcritureEnum.BANQUE,
    "cnss": TypeEcritureEnum.CNSS,
    "tva": TypeEcritureEnum.IMPOT,
    "impots": TypeEcritureEnum.IMPOT,
}

# Dictionnaire des taux de TVA reconnus pour sécuriser l'affectation
_TAUX_VALIDES = {20: TauxTVAEnum.TAUX_20, 14: TauxTVAEnum.TAUX_14,
                 10: TauxTVAEnum.TAUX_10, 7: TauxTVAEnum.TAUX_7, 0: TauxTVAEnum.TAUX_0}


def _normaliser_categorie(categorie: object | None) -> str:
    """Normalise les catégories IA, enum et libellés singulier/pluriel."""
    if categorie is None:
        return ""

    raw_value = getattr(categorie, "value", categorie)
    text = str(raw_value).strip().lower()
    text = "".join(
        char
        for char in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(char)
    )
    return text.replace("-", "_").replace(" ", "_")


def _determiner_type_ecriture(categorie: object | None) -> TypeEcritureEnum:
    """Détermine le type d'écriture depuis toutes les variantes connues."""
    normalized = _normaliser_categorie(categorie)

    mapping = {
        "achat": TypeEcritureEnum.ACHAT,
        "achats": TypeEcritureEnum.ACHAT,
        "facture_achat": TypeEcritureEnum.ACHAT,
        "factures_achat": TypeEcritureEnum.ACHAT,
        "fournisseur": TypeEcritureEnum.ACHAT,
        "fournisseurs": TypeEcritureEnum.ACHAT,
        "vente": TypeEcritureEnum.VENTE,
        "ventes": TypeEcritureEnum.VENTE,
        "facture_vente": TypeEcritureEnum.VENTE,
        "factures_vente": TypeEcritureEnum.VENTE,
        "client": TypeEcritureEnum.VENTE,
        "clients": TypeEcritureEnum.VENTE,
        "banque": TypeEcritureEnum.BANQUE,
        "releve_bancaire": TypeEcritureEnum.BANQUE,
        "cnss": TypeEcritureEnum.CNSS,
        "tva": TypeEcritureEnum.IMPOT,
        "impot": TypeEcritureEnum.IMPOT,
        "impots": TypeEcritureEnum.IMPOT,
    }
    return mapping.get(normalized, TypeEcritureEnum.AUTRE)


def _normaliser_taux_tva(valeur) -> TauxTVAEnum:
    """Convertit une valeur de TVA brute en un Enum strict, par défaut à TAUX_0."""
    if valeur is None:
        return TauxTVAEnum.TAUX_0
    try:
        entier = int(round(float(valeur)))
    except (TypeError, ValueError):
        return TauxTVAEnum.TAUX_0
    return _TAUX_VALIDES.get(entier, TauxTVAEnum.TAUX_0)


def _vers_decimal(valeur) -> Decimal | None:
    """Convertit de manière sécurisée une valeur en Decimal arrondi à 2 décimales."""
    if valeur is None:
        return None
    try:
        return Decimal(str(valeur)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception:
        return None


def _resoudre_montants(donnees: dict, taux_enum: TauxTVAEnum) -> tuple[Decimal | None, Decimal | None, Decimal, bool, str | None]:
    """
    Tente de déduire les montants HT, TVA et TTC s'il en manque certains.
    Retourne : (montant_ht, montant_tva, montant_ttc, anomalie_detectee, message_erreur)
    """
    ht = _vers_decimal(donnees.get("montant_ht"))
    tva = _vers_decimal(donnees.get("montant_tva"))
    ttc = _vers_decimal(donnees.get("montant_ttc"))
    taux_pct = Decimal(taux_enum.value) / Decimal(100)

    # Scénario 1 : On a le TTC mais pas le HT ni la TVA (Déduction par le bas)
    if ttc is not None and ht is None and tva is None:
        if taux_pct > 0:
            ht = (ttc / (1 + taux_pct)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            tva = (ttc - ht).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        else:
            ht, tva = ttc, Decimal("0.00")

    # Scénario 2 : On a le HT, on calcule le reste (Déduction par le haut)
    if ttc is None and ht is not None:
        tva = tva if tva is not None else (ht * taux_pct).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        ttc = (ht + tva).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Scénario 3 : Impossible de déterminer le TTC (Cas d'anomalie sévère)
    if ttc is None:
        # Le TTC étant obligatoire en base, on force 0.00 et on lève une anomalie
        return ht, tva, Decimal("0.00"), True, "Aucun montant total TTC détecté dans le document."

    return ht, tva, ttc, False, None


def creer_ecriture_depuis_document(db: Session, document: Document) -> EcritureComptable:
    """Crée ou met à jour l'écriture liée au document.

    Le Chrono lit la table ``documents`` alors que les pages Achats/Ventes
    lisent ``ecritures_comptables``. Cette fonction garantit qu'un document
    traité possède exactement une écriture, correctement typée achat ou vente.
    """
    donnees = document.donnees_extraites or {}

    categorie_source = (
        donnees.get("categorie")
        or donnees.get("categorie_document")
        or document.categorie
    )
    type_ecriture = _determiner_type_ecriture(categorie_source)
    taux_enum = _normaliser_taux_tva(donnees.get("taux_tva"))
    ht, tva, ttc, anomalie_montants, message_montants = _resoudre_montants(
        donnees,
        taux_enum,
    )

    anomalie_regex = bool(donnees.get("a_verifier"))
    raison_regex = donnees.get("raison_verification")
    anomalie_detectee = anomalie_montants or anomalie_regex
    if anomalie_montants and anomalie_regex:
        anomalie_details = f"{message_montants} | {raison_regex}"
    else:
        anomalie_details = message_montants or raison_regex

    date_piece_str = donnees.get("date_piece")
    date_piece: date_type | None = None
    if date_piece_str:
        try:
            date_piece = date_type.fromisoformat(str(date_piece_str))
        except ValueError:
            date_piece = None

    existing_entries = (
        db.query(EcritureComptable)
        .filter(EcritureComptable.document_id == document.id)
        .order_by(EcritureComptable.created_at.asc())
        .all()
    )

    if existing_entries:
        ecriture = existing_entries[0]
        for duplicate in existing_entries[1:]:
            db.delete(duplicate)
    else:
        ecriture = EcritureComptable(
            cabinet_id=document.cabinet_id,
            document_id=document.id,
            entreprise_id=document.entreprise_id,
            type_ecriture=type_ecriture,
            montant_ttc=ttc,
        )
        db.add(ecriture)

    ecriture.cabinet_id = document.cabinet_id
    ecriture.document_id = document.id
    ecriture.entreprise_id = document.entreprise_id
    ecriture.type_ecriture = type_ecriture
    ecriture.numero_piece = donnees.get("numero_piece")
    ecriture.date_piece = date_piece
    ecriture.tiers = donnees.get("tiers")
    ecriture.montant_ht = ht
    ecriture.taux_tva = taux_enum
    ecriture.montant_tva = tva
    ecriture.montant_ttc = ttc
    ecriture.statut_validation = (
        StatutValidationEnum.A_VERIFIER
        if anomalie_detectee
        else StatutValidationEnum.BROUILLON
    )
    ecriture.validated_by = None
    ecriture.anomalie_detectee = anomalie_detectee
    ecriture.anomalie_details = anomalie_details

    db.commit()
    db.refresh(ecriture)
    return ecriture


def creer_mouvements_bancaires(db: Session, document: Document) -> list[MouvementBancaire]:
    """Crée une ligne SQL pour chaque ligne extraite du relevé bancaire.

    Aucune ligne n'est supprimée parce qu'elle est incomplète. Quand une date,
    un type ou un montant n'a pas pu être lu, une valeur technique est utilisée
    uniquement pour respecter le schéma historique de la table et la ligne est
    marquée ``a_verifier`` dans ``document.donnees_extraites``.

    Le détail complet (date valeur, débit, crédit, texte brut, confiance et
    raison de vérification) reste toujours conservé dans le JSON du document.
    """
    from app.models.enums import TypeMouvementBancaireEnum

    if document.entreprise_id is None:
        raise ValueError(
            "Le relevé bancaire doit être rattaché à une entreprise avant "
            "la création de ses mouvements."
        )

    donnees = dict(document.donnees_extraites or {})
    raw_lines = donnees.get("lignes_bancaires")
    lignes_extraites = raw_lines if isinstance(raw_lines, list) else []

    # Sécurité anti-doublon : le retraitement d'un relevé remplace ses anciennes
    # lignes au lieu de les ajouter une seconde fois.
    db.query(MouvementBancaire).filter(
        MouvementBancaire.document_id == document.id
    ).delete(synchronize_session=False)

    mouvements_crees: list[MouvementBancaire] = []
    lignes_normalisees: list[dict] = []

    for index, raw_line in enumerate(lignes_extraites, start=1):
        ligne = dict(raw_line) if isinstance(raw_line, dict) else {
            "texte_brut": str(raw_line)
        }
        raisons: list[str] = []

        def add_reason(message: str) -> None:
            if message and message not in raisons:
                raisons.append(message)

        # Date d'opération : on privilégie la date réellement extraite. Le
        # fallback technique reste visible grâce au drapeau a_verifier.
        date_obj: date_type
        date_value = ligne.get("date_operation")
        try:
            date_obj = date_type.fromisoformat(str(date_value))
        except (TypeError, ValueError):
            date_obj = document.created_at.date()
            add_reason("Date d'opération non détectée : date d'import utilisée provisoirement.")

        debit = _vers_decimal(ligne.get("debit"))
        credit = _vers_decimal(ligne.get("credit"))
        montant = _vers_decimal(ligne.get("montant"))

        raw_type = str(ligne.get("type_mouvement") or "").strip().lower()
        if raw_type in {"credit", "crédit", "depot", "dépôt", "encaissement"}:
            mouvement_type = TypeMouvementBancaireEnum.CREDIT
        elif raw_type in {"debit", "débit", "retrait", "decaissement", "décaissement"}:
            mouvement_type = TypeMouvementBancaireEnum.DEBIT
        elif credit is not None and debit is None:
            mouvement_type = TypeMouvementBancaireEnum.CREDIT
        elif debit is not None and credit is None:
            mouvement_type = TypeMouvementBancaireEnum.DEBIT
        else:
            # Valeur technique compatible avec l'ancien schéma NOT NULL.
            mouvement_type = TypeMouvementBancaireEnum.DEBIT
            add_reason("Type débit/crédit non déterminé : débit provisoire.")

        if montant is None:
            if mouvement_type == TypeMouvementBancaireEnum.CREDIT:
                montant = credit
            else:
                montant = debit

        if montant is None:
            montant = Decimal("0.00")
            add_reason("Montant non détecté : 0,00 MAD provisoire.")

        solde = _vers_decimal(ligne.get("solde_apres_operation"))

        libelle = str(
            ligne.get("libelle_original")
            or ligne.get("libelle")
            or ligne.get("texte_brut")
            or "Ligne bancaire à vérifier"
        ).strip()
        if not libelle:
            libelle = "Ligne bancaire à vérifier"
            add_reason("Libellé non détecté.")

        reference = ligne.get("reference") or ligne.get("code_operation")
        if reference is not None:
            reference = str(reference).strip()[:100] or None

        existing_reason = ligne.get("raison_verification")
        if existing_reason:
            add_reason(str(existing_reason))

        ligne["ordre"] = int(ligne.get("ordre") or index)
        ligne["date_operation"] = date_obj.isoformat()
        ligne["libelle"] = libelle[:500]
        ligne["reference"] = reference
        ligne["type_mouvement"] = mouvement_type.name
        ligne["montant"] = float(montant)
        ligne["solde_apres_operation"] = float(solde) if solde is not None else None
        ligne["a_verifier"] = bool(raisons) or bool(ligne.get("a_verifier"))
        ligne["raison_verification"] = " | ".join(raisons) if raisons else None
        lignes_normalisees.append(ligne)

        mouvement = MouvementBancaire(
            cabinet_id=document.cabinet_id,
            document_id=document.id,
            entreprise_id=document.entreprise_id,
            date_operation=date_obj,
            libelle=libelle[:500],
            reference=reference,
            type_mouvement=mouvement_type,
            montant=montant,
            solde_apres_operation=solde,
        )
        db.add(mouvement)
        mouvements_crees.append(mouvement)

    donnees["lignes_bancaires"] = lignes_normalisees
    donnees["nombre_lignes_extraites"] = len(lignes_normalisees)

    incomplete_count = sum(1 for line in lignes_normalisees if line.get("a_verifier"))
    if incomplete_count:
        donnees["a_verifier"] = True
        message = f"{incomplete_count} ligne(s) bancaire(s) nécessitent une vérification."
        previous = str(donnees.get("raison_verification") or "").strip()
        donnees["raison_verification"] = (
            f"{previous} | {message}" if previous and message not in previous else message
        )
        donnees["extraction_bancaire_statut"] = "a_verifier"

    # Réaffectation complète obligatoire pour que SQLAlchemy détecte la
    # modification du JSONB, y compris les changements dans les sous-listes.
    document.donnees_extraites = donnees

    db.commit()
    for mouvement in mouvements_crees:
        db.refresh(mouvement)
    return mouvements_crees
