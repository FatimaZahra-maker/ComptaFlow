from app.services.bank_statement_service import normaliser_et_valider_releve


def test_preserves_duplicate_lines_and_validates_totals():
    pages = [
        {
            "page": 1,
            "banque": "Attijariwafa bank",
            "titulaire_compte": "Société Test",
            "periode_debut": "2025-05-01",
            "periode_fin": "2025-05-31",
            "solde_depart": "9 300,17",
            "solde_final": "9 500,17",
            "total_debit_imprime": "100,00",
            "total_credit_imprime": "300,00",
            "nombre_lignes_detectees": 3,
            "lignes_bancaires": [
                {
                    "date_operation": "02/05/2025",
                    "libelle_original": "FRAIS",
                    "debit": "50,00",
                    "texte_brut": "02/05 FRAIS 50,00",
                },
                {
                    "date_operation": "02/05/2025",
                    "libelle_original": "FRAIS",
                    "debit": "50,00",
                    "texte_brut": "02/05 FRAIS 50,00",
                },
                {
                    "date_operation": "03/05/2025",
                    "libelle_original": "VIREMENT REÇU",
                    "credit": "300,00",
                    "texte_brut": "03/05 VIREMENT REÇU 300,00",
                },
            ],
        }
    ]

    result = normaliser_et_valider_releve(pages)

    assert len(result["lignes_bancaires"]) == 3
    assert result["lignes_bancaires"][0]["libelle"] == "FRAIS"
    assert result["lignes_bancaires"][1]["libelle"] == "FRAIS"
    assert result["total_debit_calcule"] == 100.0
    assert result["total_credit_calcule"] == 300.0
    assert result["solde_final_calcule"] == 9500.17
    assert result["extraction_bancaire_statut"] == "valide"
    assert result["a_verifier"] is False


def test_incomplete_line_is_kept_and_marked_for_review():
    pages = [
        {
            "page": 1,
            "periode_debut": "2025-05-01",
            "periode_fin": "2025-05-31",
            "lignes_bancaires": [
                {
                    "libelle_original": "LIGNE PARTIELLE",
                    "texte_brut": "LIGNE PARTIELLE ILLISIBLE",
                }
            ],
        }
    ]

    result = normaliser_et_valider_releve(pages)

    assert len(result["lignes_bancaires"]) == 1
    line = result["lignes_bancaires"][0]
    assert line["libelle"] == "LIGNE PARTIELLE"
    assert line["a_verifier"] is True
    assert "Date d'opération" in line["raison_verification"]
    assert "Montant" in line["raison_verification"]
    assert result["a_verifier"] is True
    assert result["extraction_bancaire_statut"] == "a_verifier"