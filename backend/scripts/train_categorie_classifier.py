"""
scripts/train_categorie_classifier.py

Entraîne un classifieur ML (TF-IDF + Régression Logistique) pour
prédire la catégorie d'un document à partir de son texte OCR.

CATÉGORIES RÉDUITES (4 au lieu de 9) : vu le volume de données
disponible pour ce PFE, on regroupe les 9 catégories métier en 4
classes plus faciles à peupler avec un petit jeu de données :
- achats      (englobe : achats, fournisseurs)
- ventes      (englobe : ventes, clients)
- banque      (inchangé)
- autre       (englobe : cnss, tva, impots, divers)

Ce mapping reste un vrai exercice de classification multi-classes
supervisée, présentable avec un jeu de données limité, sans sacrifier
la rigueur (train/test split, matrice de confusion, rapport de
classification).

Usage (depuis backend/, avec l'env conda comptaflow actif) :
    python scripts/train_categorie_classifier.py

Produit : app/ml_models/categorie_classifier.joblib
"""
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent))

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
from collections import Counter

from app.core.database import SessionLocal
from app.models.document import Document

MODELE_SORTIE = Path(__file__).resolve().parent.parent / "app" / "ml_models" / "categorie_classifier.joblib"
NOMBRE_MIN_PAR_CLASSE_RECOMMANDE = 5

_MAPPING_REDUCTION = {
    "achats": "achats",
    "fournisseurs": "achats",
    "ventes": "ventes",
    "clients": "ventes",
    "banque": "banque",
    "cnss": "autre",
    "tva": "autre",
    "impots": "autre",
    "divers": "autre",
}


def charger_donnees_entrainement():
    db = SessionLocal()
    try:
        documents = (
            db.query(Document)
            .filter(Document.categorie.isnot(None), Document.texte_ocr.isnot(None))
            .all()
        )
    finally:
        db.close()

    textes, labels = [], []
    for d in documents:
        if not d.texte_ocr.strip():
            continue
        categorie_originale = d.categorie.value
        categorie_reduite = _MAPPING_REDUCTION.get(categorie_originale, "autre")
        textes.append(d.texte_ocr)
        labels.append(categorie_reduite)
    return textes, labels


def main():
    print("Chargement des documents déjà classés depuis la base...")
    textes, labels = charger_donnees_entrainement()
    print(f"{len(textes)} documents chargés (après réduction à 4 catégories).")

    compteur = Counter(labels)
    print("Répartition par catégorie (réduite) :", dict(compteur))

    classes_manquantes = set(_MAPPING_REDUCTION.values()) - set(compteur.keys())
    if classes_manquantes:
        print(f"❌ Catégories SANS AUCUN exemple : {classes_manquantes}")
        print("   Uploade et classe au moins quelques documents dans ces catégories avant de continuer.")

    classes_insuffisantes = {c: n for c, n in compteur.items() if n < NOMBRE_MIN_PAR_CLASSE_RECOMMANDE}
    if classes_insuffisantes:
        print(f"⚠️  Catégories avec moins de {NOMBRE_MIN_PAR_CLASSE_RECOMMANDE} exemples (résultats peu fiables) : {classes_insuffisantes}")

    if len(set(labels)) < 2:
        print("❌ Il faut au moins 2 catégories représentées pour entraîner un classifieur. Abandon.")
        return

    if len(textes) >= 10 and all(n >= 2 for n in compteur.values()):
        X_train, X_test, y_train, y_test = train_test_split(
            textes, labels, test_size=0.25, random_state=42, stratify=labels
        )
    else:
        print("⚠️  Trop peu de données pour un vrai split train/test -- évaluation indicative uniquement (mêmes données en train et test).")
        X_train, y_train = textes, labels
        X_test, y_test = textes, labels

    pipeline = Pipeline([
        ("tfidf", TfidfVectorizer(max_features=2000, ngram_range=(1, 2), lowercase=True)),
        ("classifieur", LogisticRegression(max_iter=1000, class_weight="balanced")),
    ])

    print("\nEntraînement en cours...")
    pipeline.fit(X_train, y_train)

    print("\n=== Évaluation ===")
    y_pred = pipeline.predict(X_test)
    print(classification_report(y_test, y_pred, zero_division=0))
    print("Matrice de confusion (ordre :", sorted(set(labels)), ") :")
    print(confusion_matrix(y_test, y_pred, labels=sorted(set(labels))))

    MODELE_SORTIE.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(pipeline, MODELE_SORTIE)
    print(f"\n✅ Modèle sauvegardé : {MODELE_SORTIE}")


if __name__ == "__main__":
    main()