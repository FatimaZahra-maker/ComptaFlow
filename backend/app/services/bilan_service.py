"""Construction d'un Bilan technique depuis le Grand Livre validé.

Cette V1 reste volontairement prudente :
- elle travaille uniquement sur les lignes comptables validées et exprimées en MAD ;
- elle classe les comptes selon les grandes classes CGNC utiles au Bilan ;
- elle déduit les amortissements/provisions reconnus (28, 29, 39) de l'actif ;
- elle ne transforme jamais un compte inconnu en rubrique arbitraire ;
- elle rapproche le résultat net du CPC avec l'écart Actif/Passif uniquement
  lorsque ce résultat ferme l'écart à 1 MAD près.

Le résultat produit est un état de contrôle technique. Il ne prétend pas être
une liasse fiscale ou un état de synthèse prêt au dépôt tant que tous les
comptes de l'entreprise et les écritures de clôture ne sont pas validés.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterable
import uuid
import unicodedata

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.compte_comptable_entreprise import CompteComptableEntreprise
from app.models.ligne_comptable import LigneComptable
from app.models.regularisation_cloture import RegularisationCloture
from app.services import cpc_service
from app.services.etat_comptable_service import ControleGrandLivreBalance, controler_lignes_validees
from app.services.plan_comptable_service import normaliser_texte

MONEY = Decimal("0.01")
ZERO = Decimal("0.00")
TOLERANCE_EQUILIBRE = Decimal("1.00")

RUBRIQUE_ACTIF_IMMOBILISE = "actif_immobilise"
RUBRIQUE_AMORT_PROV_IMMOBILISATIONS = "amortissements_provisions_immobilisations"
RUBRIQUE_ACTIF_CIRCULANT = "actif_circulant"
RUBRIQUE_PROV_ACTIF_CIRCULANT = "provisions_actif_circulant"
RUBRIQUE_TRESORERIE_ACTIF = "tresorerie_actif"
RUBRIQUE_FINANCEMENT_PERMANENT = "financement_permanent"
RUBRIQUE_PASSIF_CIRCULANT = "passif_circulant"
RUBRIQUE_TRESORERIE_PASSIF = "tresorerie_passif"
RUBRIQUE_NON_CLASSEE = "non_classee"


@dataclass(slots=True)
class BilanCompteDetail:
    compte: str
    libelle_compte: str | None
    rubrique: str
    cote: str
    debit: Decimal
    credit: Decimal
    solde_debiteur: Decimal
    solde_crediteur: Decimal
    montant_bilan: Decimal
    est_compte_correcteur: bool = False


@dataclass(slots=True)
class BilanResultat:
    entreprise_id: uuid.UUID
    annee: int
    date_cloture: date

    actif_immobilise_brut: Decimal = ZERO
    amortissements_provisions_immobilisations: Decimal = ZERO
    actif_immobilise_net: Decimal = ZERO

    actif_circulant_brut: Decimal = ZERO
    provisions_actif_circulant: Decimal = ZERO
    actif_circulant_net: Decimal = ZERO

    tresorerie_actif: Decimal = ZERO
    total_actif: Decimal = ZERO

    financement_permanent_comptabilise: Decimal = ZERO
    passif_circulant: Decimal = ZERO
    tresorerie_passif: Decimal = ZERO
    total_passif_comptable: Decimal = ZERO

    resultat_net_cpc: Decimal = ZERO
    resultat_cpc_integre: bool = False
    total_passif_technique: Decimal = ZERO

    ecart_avant_resultat_cpc: Decimal = ZERO
    ecart_bilan: Decimal = ZERO
    equilibre: bool = False

    nombre_lignes: int = 0
    nombre_comptes: int = 0
    a_verifier: bool = False
    raisons_verification: list[str] = field(default_factory=list)
    comptes: list[BilanCompteDetail] = field(default_factory=list)
    source_calcul: str = "grand_livre_valide_mad_plus_cpc"


def _money(value: object | None) -> Decimal:
    if value is None or value == "":
        return ZERO
    try:
        return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)
    except (InvalidOperation, ValueError, TypeError):
        return ZERO


def normaliser_compte(value: object | None) -> str:
    if value is None:
        return ""
    return "".join(character for character in str(value).strip() if character.isdigit())


def _normaliser_texte(value: object | None) -> str:
    if value is None:
        return ""
    text = unicodedata.normalize("NFKD", str(value))
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join(text.lower().split())


def determiner_rubrique_bilan(compte: object | None) -> tuple[str | None, str | None, bool]:
    """Retourne (rubrique, cote, compte_correcteur)."""
    numero = normaliser_compte(compte)
    if not numero:
        return None, None, False

    # Comptes correcteurs de l'actif : ils diminuent la valeur brute.
    if numero.startswith(("28", "29")):
        return RUBRIQUE_AMORT_PROV_IMMOBILISATIONS, "actif", True
    if numero.startswith("39"):
        return RUBRIQUE_PROV_ACTIF_CIRCULANT, "actif", True

    if numero.startswith("2"):
        return RUBRIQUE_ACTIF_IMMOBILISE, "actif", False
    if numero.startswith("3"):
        return RUBRIQUE_ACTIF_CIRCULANT, "actif", False
    if numero.startswith("51"):
        return RUBRIQUE_TRESORERIE_ACTIF, "actif", False

    if numero.startswith("1"):
        return RUBRIQUE_FINANCEMENT_PERMANENT, "passif", False
    if numero.startswith("4"):
        return RUBRIQUE_PASSIF_CIRCULANT, "passif", False
    if numero.startswith("55"):
        return RUBRIQUE_TRESORERIE_PASSIF, "passif", False

    # Les classes 6/7 appartiennent au CPC et ne sont pas placées directement
    # au bilan. Leur résultat est repris séparément via cpc_service.
    if numero.startswith(("6", "7")):
        return None, None, False

    return RUBRIQUE_NON_CLASSEE, None, False


def _detail_montant(
    rubrique: str,
    debit: Decimal,
    credit: Decimal,
) -> tuple[Decimal, Decimal, Decimal]:
    solde = (debit - credit).quantize(MONEY)
    solde_debiteur = max(solde, ZERO).quantize(MONEY)
    solde_crediteur = max(-solde, ZERO).quantize(MONEY)

    if rubrique in {
        RUBRIQUE_ACTIF_IMMOBILISE,
        RUBRIQUE_ACTIF_CIRCULANT,
        RUBRIQUE_TRESORERIE_ACTIF,
    }:
        montant = solde
    elif rubrique in {
        RUBRIQUE_AMORT_PROV_IMMOBILISATIONS,
        RUBRIQUE_PROV_ACTIF_CIRCULANT,
        RUBRIQUE_FINANCEMENT_PERMANENT,
        RUBRIQUE_PASSIF_CIRCULANT,
        RUBRIQUE_TRESORERIE_PASSIF,
    }:
        montant = (credit - debit).quantize(MONEY)
    else:
        montant = ZERO

    return solde_debiteur, solde_crediteur, montant


def calculer_bilan_depuis_lignes(
    *,
    entreprise_id: uuid.UUID,
    annee: int,
    lignes: Iterable[object],
    resultat_net_cpc: Decimal | int | float | str = ZERO,
    libelles_comptes: dict[str, str] | None = None,
) -> BilanResultat:
    """Calcule un Bilan technique à partir des lignes validées disponibles."""
    date_cloture = date(annee, 12, 31)
    libelles = libelles_comptes or {}
    resultat_cpc = _money(resultat_net_cpc)

    agregats: dict[str, dict[str, object]] = {}
    raisons: list[str] = []
    nombre_lignes = 0

    for ligne in lignes:
        nombre_lignes += 1
        compte = normaliser_compte(getattr(ligne, "compte", None))
        debit = _money(getattr(ligne, "debit", None))
        credit = _money(getattr(ligne, "credit", None))

        if not compte:
            message = "Une ligne validée ne contient aucun numéro de compte."
            if message not in raisons:
                raisons.append(message)
            continue

        rubrique, cote, correcteur = determiner_rubrique_bilan(compte)

        # Classes 6/7 : ignorées ici, car le CPC fournit le résultat net.
        if rubrique is None:
            continue

        if rubrique == RUBRIQUE_NON_CLASSEE:
            message = (
                f"Compte {compte} non reconnu par le moteur Bilan V1 : "
                "classement manuel requis."
            )
            if message not in raisons:
                raisons.append(message)

        current = agregats.setdefault(
            compte,
            {
                "rubrique": rubrique,
                "cote": cote,
                "correcteur": correcteur,
                "debit": ZERO,
                "credit": ZERO,
            },
        )
        current["debit"] = (_money(current["debit"]) + debit).quantize(MONEY)
        current["credit"] = (_money(current["credit"]) + credit).quantize(MONEY)

    details: list[BilanCompteDetail] = []
    totals: dict[str, Decimal] = {
        RUBRIQUE_ACTIF_IMMOBILISE: ZERO,
        RUBRIQUE_AMORT_PROV_IMMOBILISATIONS: ZERO,
        RUBRIQUE_ACTIF_CIRCULANT: ZERO,
        RUBRIQUE_PROV_ACTIF_CIRCULANT: ZERO,
        RUBRIQUE_TRESORERIE_ACTIF: ZERO,
        RUBRIQUE_FINANCEMENT_PERMANENT: ZERO,
        RUBRIQUE_PASSIF_CIRCULANT: ZERO,
        RUBRIQUE_TRESORERIE_PASSIF: ZERO,
    }

    for compte in sorted(agregats):
        row = agregats[compte]
        rubrique = str(row["rubrique"])
        cote = str(row["cote"] or "non_classe")
        debit = _money(row["debit"])
        credit = _money(row["credit"])
        solde_debiteur, solde_crediteur, montant = _detail_montant(
            rubrique,
            debit,
            credit,
        )

        if rubrique in totals:
            totals[rubrique] = (totals[rubrique] + montant).quantize(MONEY)

        details.append(
            BilanCompteDetail(
                compte=compte,
                libelle_compte=libelles.get(compte),
                rubrique=rubrique,
                cote=cote,
                debit=debit,
                credit=credit,
                solde_debiteur=solde_debiteur,
                solde_crediteur=solde_crediteur,
                montant_bilan=montant,
                est_compte_correcteur=bool(row["correcteur"]),
            )
        )

    actif_immobilise_brut = totals[RUBRIQUE_ACTIF_IMMOBILISE]
    amort_prov_immo = totals[RUBRIQUE_AMORT_PROV_IMMOBILISATIONS]
    actif_immobilise_net = (actif_immobilise_brut - amort_prov_immo).quantize(MONEY)

    actif_circulant_brut = totals[RUBRIQUE_ACTIF_CIRCULANT]
    provisions_actif = totals[RUBRIQUE_PROV_ACTIF_CIRCULANT]
    actif_circulant_net = (actif_circulant_brut - provisions_actif).quantize(MONEY)

    tresorerie_actif = totals[RUBRIQUE_TRESORERIE_ACTIF]
    total_actif = (
        actif_immobilise_net + actif_circulant_net + tresorerie_actif
    ).quantize(MONEY)

    financement = totals[RUBRIQUE_FINANCEMENT_PERMANENT]
    passif_circulant = totals[RUBRIQUE_PASSIF_CIRCULANT]
    tresorerie_passif = totals[RUBRIQUE_TRESORERIE_PASSIF]
    total_passif_comptable = (
        financement + passif_circulant + tresorerie_passif
    ).quantize(MONEY)

    ecart_avant = (total_actif - total_passif_comptable).quantize(MONEY)
    ecart_avec_cpc = (
        total_actif - (total_passif_comptable + resultat_cpc)
    ).quantize(MONEY)

    # On n'intègre le CPC que s'il ferme effectivement l'écart. Cette règle
    # évite de doubler le résultat lorsqu'une écriture de clôture existe déjà.
    resultat_cpc_integre = (
        abs(ecart_avant) > TOLERANCE_EQUILIBRE
        and abs(ecart_avec_cpc) <= TOLERANCE_EQUILIBRE
    )

    total_passif_technique = (
        total_passif_comptable + resultat_cpc
        if resultat_cpc_integre
        else total_passif_comptable
    ).quantize(MONEY)

    ecart_bilan = (total_actif - total_passif_technique).quantize(MONEY)
    equilibre = abs(ecart_bilan) <= TOLERANCE_EQUILIBRE

    if not equilibre:
        raisons.append(
            "Le total Actif et le total Passif technique ne sont pas équilibrés "
            f"(écart {ecart_bilan} MAD)."
        )

    # Un compte inconnu de classe 5 est particulièrement sensible : il peut
    # représenter une sous-rubrique de trésorerie non encore prise en charge.
    if any(
        item.rubrique == RUBRIQUE_NON_CLASSEE and item.compte.startswith("5")
        for item in details
    ):
        message = (
            "Au moins un compte de classe 5 n'est pas classé en trésorerie-actif "
            "(51) ou trésorerie-passif (55). Vérification du plan comptable requise."
        )
        if message not in raisons:
            raisons.append(message)

    return BilanResultat(
        entreprise_id=entreprise_id,
        annee=annee,
        date_cloture=date_cloture,
        actif_immobilise_brut=actif_immobilise_brut,
        amortissements_provisions_immobilisations=amort_prov_immo,
        actif_immobilise_net=actif_immobilise_net,
        actif_circulant_brut=actif_circulant_brut,
        provisions_actif_circulant=provisions_actif,
        actif_circulant_net=actif_circulant_net,
        tresorerie_actif=tresorerie_actif,
        total_actif=total_actif,
        financement_permanent_comptabilise=financement,
        passif_circulant=passif_circulant,
        tresorerie_passif=tresorerie_passif,
        total_passif_comptable=total_passif_comptable,
        resultat_net_cpc=resultat_cpc,
        resultat_cpc_integre=resultat_cpc_integre,
        total_passif_technique=total_passif_technique,
        ecart_avant_resultat_cpc=ecart_avant,
        ecart_bilan=ecart_bilan,
        equilibre=equilibre,
        nombre_lignes=nombre_lignes,
        nombre_comptes=len(details),
        a_verifier=bool(raisons),
        raisons_verification=raisons,
        comptes=details,
    )


def calculer_bilan(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    annee: int,
) -> BilanResultat:
    """Charge les lignes jusqu'à la clôture puis calcule le Bilan technique."""
    date_fin = date(annee, 12, 31)

    lignes = db.execute(
        select(LigneComptable)
        .where(
            LigneComptable.cabinet_id == cabinet_id,
            LigneComptable.entreprise_id == entreprise_id,
            LigneComptable.est_validee.is_(True),
            LigneComptable.date_ecriture <= date_fin,
        )
        .order_by(LigneComptable.compte, LigneComptable.date_ecriture)
    ).scalars().all()

    comptes_plan = db.execute(
        select(CompteComptableEntreprise).where(
            CompteComptableEntreprise.cabinet_id == cabinet_id,
            CompteComptableEntreprise.entreprise_id == entreprise_id,
            CompteComptableEntreprise.is_active.is_(True),
        )
    ).scalars().all()

    libelles = {
        normaliser_compte(compte.numero_compte): compte.libelle
        for compte in comptes_plan
        if normaliser_compte(compte.numero_compte)
    }

    cpc = cpc_service.calculer_cpc(
        db,
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        annee=annee,
    )

    return calculer_bilan_depuis_lignes(
        entreprise_id=entreprise_id,
        annee=annee,
        lignes=lignes,
        resultat_net_cpc=cpc.resultat_net,
        libelles_comptes=libelles,
    )


@dataclass(slots=True)
class BilanRubriqueV2:
    code: str
    libelle: str
    montant: Decimal


@dataclass(slots=True)
class ControleResultatBilanV2:
    resultat_cpc: Decimal
    resultat_comptabilise: Decimal
    resultat_non_affecte: Decimal
    deja_comptabilise: bool
    coherent: bool
    statut: str


@dataclass(slots=True)
class BilanV2Resultat:
    entreprise_id: uuid.UUID
    exercice: int
    date_cloture: date
    actif: list[BilanRubriqueV2]
    passif: list[BilanRubriqueV2]
    total_actif: Decimal
    total_passif: Decimal
    ecart: Decimal
    resultat_cpc: Decimal
    resultat_non_affecte: Decimal
    resultat_deja_comptabilise: bool
    bilan_equilibre: bool
    controle_resultat: ControleResultatBilanV2
    controle_grand_livre_balance: ControleGrandLivreBalance
    comptes: list[BilanCompteDetail]
    comptes_non_classes: list[BilanCompteDetail]
    anomalies: list[str]
    statut: str
    nombre_lignes: int
    nombre_comptes: int
    source_calcul: str = "lignes_validees_grand_livre_balance_et_cpc_v2"


def calculer_bilan_v2_depuis_lignes(
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    exercice: int,
    lignes: Iterable[object],
    resultat_net_cpc: Decimal | int | float | str = ZERO,
    comptes_resultat_configures: set[str] | None = None,
    libelles_comptes: dict[str, str] | None = None,
    anomalies_cpc: Iterable[str] = (),
) -> BilanV2Resultat:
    controle = controler_lignes_validees(
        lignes,
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        date_fin=date(exercice, 12, 31),
    )
    # Le moteur V1 reste disponible, mais V2 lui passe volontairement zero :
    # aucune decision d'affectation ne depend de la fermeture de l'ecart.
    base = calculer_bilan_depuis_lignes(
        entreprise_id=entreprise_id,
        annee=exercice,
        lignes=controle.lignes,
        resultat_net_cpc=ZERO,
        libelles_comptes=libelles_comptes,
    )
    anomalies = list(controle.anomalies)
    non_classes = [item for item in base.comptes if item.rubrique == RUBRIQUE_NON_CLASSEE]
    for item in non_classes:
        message = f"Compte de bilan {item.compte} non classe: classement manuel requis."
        if message not in anomalies:
            anomalies.append(message)

    rubriques_actif_normales = {
        RUBRIQUE_ACTIF_IMMOBILISE, RUBRIQUE_ACTIF_CIRCULANT, RUBRIQUE_TRESORERIE_ACTIF,
    }
    rubriques_correctrices = {
        RUBRIQUE_AMORT_PROV_IMMOBILISATIONS, RUBRIQUE_PROV_ACTIF_CIRCULANT,
    }
    rubriques_passif = {
        RUBRIQUE_FINANCEMENT_PERMANENT, RUBRIQUE_PASSIF_CIRCULANT, RUBRIQUE_TRESORERIE_PASSIF,
    }
    for item in base.comptes:
        sens_inattendu = (
            (item.rubrique in rubriques_actif_normales and item.montant_bilan < ZERO)
            or (item.rubrique in rubriques_correctrices and item.montant_bilan < ZERO)
            or (item.rubrique in rubriques_passif and item.montant_bilan < ZERO)
        )
        if sens_inattendu:
            anomalies.append(f"Le compte {item.compte} presente un sens inattendu pour {item.rubrique}.")

    for message in anomalies_cpc:
        detail = f"CPC: {message}"
        if detail not in anomalies:
            anomalies.append(detail)

    resultat_cpc = _money(resultat_net_cpc)
    comptes_resultat = {normaliser_compte(value) for value in (comptes_resultat_configures or set())}
    comptes_resultat.discard("")
    details_resultat = [
        item for item in base.comptes
        if item.compte in comptes_resultat and item.montant_bilan != ZERO
    ]
    resultat_deja_comptabilise = bool(details_resultat)
    resultat_comptabilise = sum((item.montant_bilan for item in details_resultat), ZERO).quantize(MONEY)
    if len(details_resultat) > 1:
        anomalies.append("Plusieurs comptes explicites de resultat portent un solde: affectation ambigue.")

    if resultat_deja_comptabilise:
        resultat_non_affecte = ZERO
        resultat_coherent = abs(resultat_comptabilise - resultat_cpc) <= TOLERANCE_EQUILIBRE
        statut_resultat = "comptabilise_coherent" if resultat_coherent else "comptabilise_incoherent"
        if not resultat_coherent:
            anomalies.append(
                f"Resultat CPC incoherent avec le resultat comptabilise: {resultat_cpc} != {resultat_comptabilise}."
            )
    else:
        resultat_non_affecte = resultat_cpc
        resultat_coherent = True
        statut_resultat = "non_affecte" if resultat_cpc != ZERO else "sans_resultat"
        if resultat_cpc != ZERO:
            anomalies.append(
                "Le resultat CPC n'est pas encore comptabilise: il est presente separement en resultat_non_affecte."
            )

    total_passif = (base.total_passif_comptable + resultat_non_affecte).quantize(MONEY)
    ecart = (base.total_actif - total_passif).quantize(MONEY)
    bilan_equilibre = abs(ecart) <= TOLERANCE_EQUILIBRE
    if not bilan_equilibre:
        anomalies.append(f"Bilan non equilibre: ecart Actif - Passif de {ecart} MAD.")

    actif = [
        BilanRubriqueV2("actif_immobilise_brut", "Actif immobilise brut", base.actif_immobilise_brut),
        BilanRubriqueV2("amortissements_provisions_immobilisations", "Amortissements et provisions immobilisations", -base.amortissements_provisions_immobilisations),
        BilanRubriqueV2("actif_immobilise_net", "Actif immobilise net", base.actif_immobilise_net),
        BilanRubriqueV2("actif_circulant_brut", "Actif circulant brut", base.actif_circulant_brut),
        BilanRubriqueV2("provisions_actif_circulant", "Provisions actif circulant", -base.provisions_actif_circulant),
        BilanRubriqueV2("actif_circulant_net", "Actif circulant net", base.actif_circulant_net),
        BilanRubriqueV2("tresorerie_actif", "Tresorerie actif", base.tresorerie_actif),
    ]
    passif = [
        BilanRubriqueV2("financement_permanent", "Financement permanent", base.financement_permanent_comptabilise),
        BilanRubriqueV2("passif_circulant", "Passif circulant", base.passif_circulant),
        BilanRubriqueV2("tresorerie_passif", "Tresorerie passif", base.tresorerie_passif),
        BilanRubriqueV2("resultat_non_affecte", "Resultat non affecte", resultat_non_affecte),
    ]
    return BilanV2Resultat(
        entreprise_id=entreprise_id,
        exercice=exercice,
        date_cloture=date(exercice, 12, 31),
        actif=actif,
        passif=passif,
        total_actif=base.total_actif,
        total_passif=total_passif,
        ecart=ecart,
        resultat_cpc=resultat_cpc,
        resultat_non_affecte=resultat_non_affecte,
        resultat_deja_comptabilise=resultat_deja_comptabilise,
        bilan_equilibre=bilan_equilibre,
        controle_resultat=ControleResultatBilanV2(
            resultat_cpc=resultat_cpc,
            resultat_comptabilise=resultat_comptabilise,
            resultat_non_affecte=resultat_non_affecte,
            deja_comptabilise=resultat_deja_comptabilise,
            coherent=resultat_coherent,
            statut=statut_resultat,
        ),
        controle_grand_livre_balance=controle.controle,
        comptes=base.comptes,
        comptes_non_classes=non_classes,
        anomalies=anomalies,
        statut="a_verifier" if anomalies else "ok",
        nombre_lignes=len(controle.lignes),
        nombre_comptes=base.nombre_comptes,
    )


def calculer_bilan_v2(
    db: Session,
    *,
    cabinet_id: uuid.UUID,
    entreprise_id: uuid.UUID,
    exercice: int,
) -> BilanV2Resultat:
    lignes = db.execute(select(LigneComptable).where(
        LigneComptable.cabinet_id == cabinet_id,
        LigneComptable.entreprise_id == entreprise_id,
        LigneComptable.est_validee.is_(True),
        LigneComptable.date_ecriture <= date(exercice, 12, 31),
    ).order_by(LigneComptable.date_ecriture, LigneComptable.compte)).scalars().all()
    comptes_plan = db.execute(select(CompteComptableEntreprise).where(
        CompteComptableEntreprise.cabinet_id == cabinet_id,
        CompteComptableEntreprise.entreprise_id == entreprise_id,
        CompteComptableEntreprise.is_active.is_(True),
    )).scalars().all()
    labels = {
        normaliser_compte(compte.numero_compte): compte.libelle
        for compte in comptes_plan if normaliser_compte(compte.numero_compte)
    }
    comptes_resultat = {
        normaliser_compte(compte.numero_compte)
        for compte in comptes_plan
        if normaliser_texte(compte.nature_comptable) in {"resultat_exercice", "resultat_net"}
        and normaliser_compte(compte.numero_compte).startswith("1")
    }
    clotures_resultat = db.execute(select(RegularisationCloture).where(
        RegularisationCloture.cabinet_id == cabinet_id,
        RegularisationCloture.entreprise_id == entreprise_id,
        RegularisationCloture.exercice == exercice,
        RegularisationCloture.type_regularisation == "resultat_cloture",
        RegularisationCloture.statut == "comptabilisee",
    )).scalars().all()
    for cloture in clotures_resultat:
        for compte in (cloture.compte_debit, cloture.compte_credit):
            numero = normaliser_compte(compte)
            if numero.startswith("1"):
                comptes_resultat.add(numero)

    cpc = cpc_service.calculer_cpc_v2(
        db, cabinet_id=cabinet_id, entreprise_id=entreprise_id, exercice=exercice
    )
    resultat_net = next(item.montant_n for item in cpc.resultats if item.code == "resultat_net")
    return calculer_bilan_v2_depuis_lignes(
        cabinet_id=cabinet_id,
        entreprise_id=entreprise_id,
        exercice=exercice,
        lignes=lignes,
        resultat_net_cpc=resultat_net,
        comptes_resultat_configures=comptes_resultat,
        libelles_comptes=labels,
        anomalies_cpc=cpc.anomalies,
    )
