import uuid
from decimal import Decimal

from app.schemas.document_detail import EcritureResumeOut


def test_resume_document_expose_les_comptes_modifiables():
    resume = EcritureResumeOut(
        id=uuid.uuid4(),
        type_ecriture="achat",
        montant_ttc=Decimal("120.00"),
        statut_validation="a_verifier",
        compte_tiers="441100000000",
        compte_ht="611100000000",
        compte_tva="345520000000",
    )

    assert resume.compte_tiers == "441100000000"
    assert resume.compte_ht == "611100000000"
    assert resume.compte_tva == "345520000000"
