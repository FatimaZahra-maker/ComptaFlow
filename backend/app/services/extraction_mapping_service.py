"""Normalisation fournisseur-neutre des champs structurés extraits."""

from app.services.regex_extraction_service import verifier_coherence_montants


def construire_donnees_extraites(champs: dict) -> dict:
    """Adapte les champs au pipeline sans reconstruire HT, TVA ou TTC."""
    donnees = {
        "nom_fournisseur": champs.get("nom_fournisseur"),
        "ice_fournisseur": champs.get("ice_fournisseur"),
        "if_fournisseur": champs.get("if_fournisseur"),
        "rc_fournisseur": champs.get("rc_fournisseur"),
        "nom_client": champs.get("nom_client"),
        "ice_client": champs.get("ice_client"),
        "if_client": champs.get("if_client"),
        "rc_client": champs.get("rc_client"),
        "nom_entreprise": champs.get("nom_fournisseur"),
        "ice": champs.get("ice_fournisseur"),
        "identifiant_fiscal": champs.get("if_fournisseur"),
        "rc": champs.get("rc_fournisseur"),
        "type_document": champs.get("categorie_document") or "autre",
        "categorie": "divers",
        "date_piece": champs.get("date_piece"),
        "numero_piece": champs.get("numero_piece"),
        "tiers": champs.get("nom_client") or champs.get("nom_fournisseur"),
        "nature_comptable": champs.get("nature_comptable"),
        "montant_ht": champs.get("montant_ht"),
        "taux_tva": champs.get("taux_tva"),
        "montant_tva": champs.get("montant_tva"),
        "montant_ttc": champs.get("montant_ttc"),
        "devise": champs.get("devise"),
        "confiance_par_champ": {
            cle: (0.90 if champs.get(cle) is not None else 0.0)
            for cle in (
                "nom_fournisseur", "ice_fournisseur", "nom_client", "ice_client",
                "date_piece", "numero_piece", "montant_ht", "taux_tva",
                "montant_tva", "montant_ttc",
            )
        },
        "enrichissement_ia_statut": "termine",
    }
    return verifier_coherence_montants(donnees)
