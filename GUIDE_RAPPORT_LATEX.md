# Rapport LaTeX ComptaFlow

Le rapport principal est `rapport_comptaflow.tex`.

## Champs à remplir

Au début du fichier, renseigner les commandes suivantes sans modifier le reste du document :

```tex
\newcommand{\Auteur}{RADOUI Fatima Zahra}
\newcommand{\Formation}{Genie Informatique}
\newcommand{\Etablissement}{ENSA de berrchide }
\newcommand{\EntrepriseAccueil}{Seguribat}
\newcommand{\EncadrantPedagogique}{Mr.Dhaj}
\newcommand{\EncadrantEntreprise}{Mr.Faiz}
\newcommand{\AnneeUniversitaire}{2025--2026}
\newcommand{\DateSoutenance}{...}
\newcommand{\PeriodeProjet}{1 juillet- 30 juillet}
```

Rechercher ensuite `à compléter` et les cellules vides pour ajouter les informations personnelles qui ne figurent pas dans le dépôt.

## Captures d'écran

Créer un dossier `captures` à côté du fichier `.tex`, puis y déposer :

- `dashboard.png`
- `import.png`
- `chronos.png`
- `document_detail.png`
- `plan_comptable.png`
- `comptes_bancaires.png`
- `banque_v2.png`
- `grand_livre.png`
- `cpc_bilan.png`
- `precloture.png`
- `rappels.png`

Le document compile même si ces images sont absentes : un cadre de remplacement apparaît à leur place. Utiliser uniquement des données de démonstration ou anonymiser les informations sensibles.

## Logiciel nécessaire

Installer une distribution LaTeX complète :

- Windows : MiKTeX ;
- alternative : TeX Live.

L'extension VS Code `LaTeX Workshop` est pratique mais facultative. Elle ne remplace pas MiKTeX ou TeX Live.

Compilation PowerShell depuis la racine du dépôt :

```powershell
pdflatex rapport_comptaflow.tex
pdflatex rapport_comptaflow.tex
```

Deux passes sont nécessaires pour actualiser le sommaire et les listes. Avec `latexmk` :

```powershell
latexmk -pdf rapport_comptaflow.tex
```
