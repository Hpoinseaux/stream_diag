# Diag360 Streamlit App

Application Streamlit permettant d'explorer les scores d'indicateurs Diag360 à partir des fichiers CSV/XLSX fournis.

## Structure du dossier

- `app.py` : point d'entrée Streamlit.
- `scoring_diag360.py` : fonctions utilitaires de scoring.
- `source/` : référentiels utilisés par l'application (paramètres, mappings, etc.).
- `score_indicateurs.csv`: données nécessaires au calcul et à l'affichage.
- `requirements.txt` : dépendances Python du projet.

## Pré-requis

- Python ≥ 3.10 (recommandé 3.11)
- [Streamlit](https://streamlit.io/) et dépendances listées dans `requirements.txt`

## Installation locale

```bash
# 1. Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate

# 2. Installer les dépendances
pip install --upgrade pip
pip install -r requirements.txt

# 3. Lancer l'application
streamlit run app.py
```

L'application lit les fichiers présents localement dans le dossier `source/` et les classeurs CSV/XLSX adjacents. Vérifiez que les fichiers attendus sont bien présents avant d'exécuter Streamlit.


