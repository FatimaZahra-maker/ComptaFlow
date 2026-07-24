"""
app/services/company_service.py

Identification de l'entreprise ET détermination de la direction
comptable (achats vs ventes) en comparant fournisseur ET client aux
entreprises déjà connues du cabinet -- c'est la seule façon fiable de
savoir si le document est un achat ou une vente : si l'ÉMETTEUR
(fournisseur) de la facture correspond à une entreprise du cabinet,
c'est une VENTE (elle a facturé quelqu'un) ; si c'est le DESTINATAIRE
(client) qui correspond, c'est un ACHAT (elle a reçu une facture).
"""
import uuid
from sqlalchemy.orm import Session

from app.models.entreprise import Entreprise


def _rechercher_entreprise(db: Session, cabinet_id: uuid.UUID, ice, identifiant_fiscal, rc, nom) -> Entreprise | None:
    if ice:
        e = db.query(Entreprise).filter_by(cabinet_id=cabinet_id, ice=ice).first()
        if e:
            return e
    if identifiant_fiscal:
        e = db.query(Entreprise).filter_by(cabinet_id=cabinet_id, identifiant_fiscal=identifiant_fiscal).first()
        if e:
            return e
    if rc:
        e = db.query(Entreprise).filter_by(cabinet_id=cabinet_id, rc=rc).first()
        if e:
            return e
    if nom:
        e = db.query(Entreprise).filter_by(cabinet_id=cabinet_id, nom=nom).first()
        if e:
            return e
    return None


def _creer_entreprise(db: Session, cabinet_id: uuid.UUID, ice, identifiant_fiscal, rc, nom) -> Entreprise:
    entreprise = Entreprise(
        cabinet_id=cabinet_id,
        nom=nom or "Entreprise à identifier",
        ice=ice,
        identifiant_fiscal=identifiant_fiscal,
        rc=rc,
        creee_automatiquement=True,
    )
    db.add(entreprise)
    db.commit()
    db.refresh(entreprise)
    return entreprise


def identifier_ou_creer_entreprise(db: Session, cabinet_id: uuid.UUID, donnees: dict) -> Entreprise:
    """Conservée pour compatibilité (relevés bancaires, CNSS, TVA --
    documents à une seule partie, pas de notion achats/ventes)."""
    return _rechercher_entreprise(
        db, cabinet_id, donnees.get("ice"), donnees.get("identifiant_fiscal"),
        donnees.get("rc"), donnees.get("nom_entreprise"),
    ) or _creer_entreprise(
        db, cabinet_id, donnees.get("ice"), donnees.get("identifiant_fiscal"),
        donnees.get("rc"), donnees.get("nom_entreprise"),
    )


def identifier_entreprise_et_direction(db: Session, cabinet_id: uuid.UUID, donnees: dict) -> tuple[Entreprise, str | None, str | None]:
    """
    Retourne (entreprise_du_cabinet, categorie_direction, tiers_nom).
    categorie_direction vaut "ventes", "achats", ou None si la
    direction n'a pas pu être déterminée avec certitude (dans ce cas
    l'appelant garde la catégorie déjà proposée par le classifieur/IA).
    """
    type_doc = donnees.get("type_document")

    # Documents à une seule partie -- pas de logique achats/ventes.
    if type_doc in ("releve_bancaire", "avis_cnss", "avis_tva"):
        entreprise = identifier_ou_creer_entreprise(db, cabinet_id, donnees)
        return entreprise, None, None

    fournisseur = _rechercher_entreprise(
        db, cabinet_id, donnees.get("ice_fournisseur"), donnees.get("if_fournisseur"),
        donnees.get("rc_fournisseur"), donnees.get("nom_fournisseur"),
    )
    client = _rechercher_entreprise(
        db, cabinet_id, donnees.get("ice_client"), donnees.get("if_client"),
        donnees.get("rc_client"), donnees.get("nom_client"),
    )

    if fournisseur is not None and client is None:
        # L'émetteur est une entreprise du cabinet -> elle a VENDU.
        return fournisseur, "ventes", donnees.get("nom_client")

    if client is not None and fournisseur is None:
        # Le destinataire est une entreprise du cabinet -> elle a ACHETÉ.
        return client, "achats", donnees.get("nom_fournisseur")

    if fournisseur is not None and client is not None:
        # Les deux existent déjà (rare, ex: deux filiales du même
        # cabinet) -- on privilégie le fournisseur comme entreprise
        # rattachée, direction = vente de son point de vue.
        return fournisseur, "ventes", donnees.get("nom_client")

    # Ni l'un ni l'autre n'est connu -- on crée l'entreprise à partir du
    # FOURNISSEUR par défaut (comportement historique), direction
    # indéterminée : on laisse la catégorie déjà proposée décider.
    entreprise = _creer_entreprise(
        db, cabinet_id, donnees.get("ice_fournisseur"), donnees.get("if_fournisseur"),
        donnees.get("rc_fournisseur"), donnees.get("nom_fournisseur"),
    )
    return entreprise, None, donnees.get("nom_client") or donnees.get("nom_fournisseur")