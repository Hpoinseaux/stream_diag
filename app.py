import re
import unicodedata
from pathlib import Path

import pandas as pd
import streamlit as st

from scoring_diag360 import y

BASE_DIR = Path(__file__).resolve().parent
SOURCE_DIR = BASE_DIR / "source"
PARAMS_PATH = SOURCE_DIR / "Parametres_indicateurs.csv"
EPCI_PATH = SOURCE_DIR / "epci_membres .csv"
EXTERNAL_SCORES_CSV = BASE_DIR / "score_indicateurs.csv"
MAPPING_PATH = SOURCE_DIR / "Répartition_moyenne.csv"
INDICATOR_COL_PATTERN = re.compile(r"^i\d{3}", re.IGNORECASE)


@st.cache_data(show_spinner=False)
def load_epci_choices() -> pd.DataFrame:
    df = pd.read_csv(EPCI_PATH, dtype=str, low_memory=False)
    df = df[["siren", "epci_nom"]].dropna()
    df["siren"] = df["siren"].astype(str).str.strip()
    df["epci_nom"] = df["epci_nom"].astype(str).str.strip()
    df = df.drop_duplicates(subset=["siren", "epci_nom"]).sort_values("epci_nom")
    return df


@st.cache_data(show_spinner=False)
def load_params() -> pd.DataFrame:
    df = pd.read_csv(PARAMS_PATH, dtype=str, low_memory=False)
    if "ID_indicateurs" in df.columns and "ID_indicateur" not in df.columns:
        df = df.rename(columns={"ID_indicateurs": "ID_indicateur"})
    if "ID_indicateur" in df.columns:
        df["ID_indicateur"] = df["ID_indicateur"].astype(str).str.strip().str.lower()
    return df


@st.cache_data(show_spinner=False)
def load_mapping() -> pd.DataFrame:
    return pd.read_csv(MAPPING_PATH, dtype=str, low_memory=False)


def load_external_coeffs(file: st.runtime.uploaded_file_manager.UploadedFile) -> pd.DataFrame:
    if file is None:
        raise ValueError("Aucun fichier de coefficients externes fourni.")

    file.seek(0)
    df = pd.read_excel(file, dtype=str)
    if "ID_indicateurs" in df.columns and "ID_indicateur" not in df.columns:
        df = df.rename(columns={"ID_indicateurs": "ID_indicateur"})
    df = df.rename(columns=str.strip)
    if "ID_indicateur" not in df.columns:
        raise ValueError("La colonne ID_indicateur est absente du fichier des coefficients externes.")
    df["ID_indicateur"] = df["ID_indicateur"].astype(str).str.strip().str.lower()
    df["Exclusion"] = df.get("Exclusion", "Non").astype(str)
    df["Coef_ponderation"] = df.get("Coef_ponderation", 1).astype(str)
    return df[["ID_indicateur", "Exclusion", "Coef_ponderation"]]


@st.cache_data(show_spinner=False)
def load_external_scores_dataset() -> pd.DataFrame:
    df = pd.read_csv(EXTERNAL_SCORES_CSV, dtype=str, low_memory=False)
    for col in ("dept", "siren", "epci_nom"):
        if col in df.columns:
            df[col] = df[col].astype(str).str.strip()
    return df


def normalize_text(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value)
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return text.lower().strip()


def normalize_col(value: object) -> str:
    text = normalize_text(value)
    return (
        text.replace(" ", "")
        .replace("_", "")
        .replace("-", "")
        .replace("/", "")
    )


def to_float(value: object) -> float | None:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = str(value).strip()
    if not text or text.lower() in {"nan", "none", "na", "/"}:
        return None
    text = text.replace(" ", "").replace(",", ".")
    try:
        return float(text)
    except ValueError:
        return None


def normalise_code(value: object) -> str | None:
    text = normalize_text(value)
    if not text:
        return None
    if text.endswith(".0"):
        text = text[:-2]
    return text


def find_column(columns, candidates: list[str]) -> str | None:
    normalized = {normalize_col(col): col for col in columns}
    for candidate in candidates:
        found = normalized.get(normalize_col(candidate))
        if found:
            return found
    return None


def is_yes(value: object) -> bool:
    return normalize_text(value) in {"oui", "yes", "y", "1", "x", "true"}


def clamp_score(value: float | None) -> float | None:
    if value is None or pd.isna(value):
        return None
    return max(0.0, min(100.0, float(value)))


def to_int_score(value: float | None) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(round(clamp_score(value)))


def score_from_value(value: object, x_min: object, x_max: object) -> float | None:
    val = to_float(value)
    x_min_val = to_float(x_min)
    x_max_val = to_float(x_max)
    if val is None or x_min_val is None or x_max_val is None:
        return None
    return clamp_score(y(val, x_min_val, x_max_val, 0) * 100)


def build_scored_internal(df: pd.DataFrame, params: pd.DataFrame) -> pd.DataFrame:
    id_col = find_column(df.columns, ["ID_indicateur", "ID_indicateurs"])
    value_col = find_column(df.columns, ["Valeur"])
    score_col = find_column(df.columns, ["Score"])
    calc_col = find_column(df.columns, ["Calcul_scoring_necessaire"])
    excl_col = find_column(df.columns, ["Exclusion"])
    coef_col = find_column(df.columns, ["Coef_ponderation", "Coef_pondération"])

    if not id_col or not value_col or not score_col or not calc_col:
        raise ValueError("Colonnes manquantes dans le fichier epci_22.")

    params_id_col = find_column(params.columns, ["ID_indicateur", "ID_indicateurs"])
    xmin_col = find_column(params.columns, ["Valeur-borne Score=0", "Valeur borne Score=0"])
    xmax_col = find_column(params.columns, ["Valeur-borne Score=100", "Valeur borne Score=100"])
    if not params_id_col or not xmin_col or not xmax_col:
        raise ValueError("Colonnes manquantes dans Parametres_indicateurs.csv.")

    params_lookup = params.set_index(params_id_col)[[xmin_col, xmax_col]]
    params_lookup.index = params_lookup.index.astype(str).str.strip().str.lower()

    scored = df.copy()
    scored[id_col] = scored[id_col].astype(str).str.strip().str.lower()
    new_scores = []
    for _, row in scored.iterrows():
        if is_yes(row.get(calc_col)):
            indicator_id = normalize_text(row.get(id_col))
            if indicator_id and indicator_id in params_lookup.index:
                x_min = params_lookup.loc[indicator_id, xmin_col]
                x_max = params_lookup.loc[indicator_id, xmax_col]
                new_score = score_from_value(row.get(value_col), x_min, x_max)
            else:
                new_score = None
            new_scores.append(new_score)
        else:
            new_scores.append(to_float(row.get(score_col)))
    scored[score_col] = new_scores

    return scored[[id_col, excl_col, coef_col, score_col]].rename(
        columns={
            id_col: "ID_indicateur",
            excl_col: "Exclusion",
            coef_col: "Coef_ponderation",
            score_col: "Score",
        }
    )


def load_external_scores(epci_siren: str, dataset: pd.DataFrame) -> dict[str, float]:
    if "siren" not in dataset.columns:
        raise ValueError("La colonne siren est absente de score_indicateurs.csv.")

    normalized = normalise_code(epci_siren)
    dataset = dataset.copy()
    dataset["_id_epci"] = dataset["siren"].apply(normalise_code)
    row = dataset[dataset["_id_epci"] == normalized].head(1)
    if row.empty:
        return {}

    row = row.iloc[0]
    scores = {}
    for col in dataset.columns:
        if INDICATOR_COL_PATTERN.match(normalize_text(col)):
            indicator_id = normalize_text(col)
            scores[indicator_id] = to_float(row.get(col))
    return scores


def build_external_table(scores: dict[str, float], coeffs: pd.DataFrame) -> pd.DataFrame:
    df = coeffs.copy()
    df["Score"] = df["ID_indicateur"].apply(lambda x: scores.get(normalize_text(x)))
    return df


def merge_tables(internal: pd.DataFrame, external: pd.DataFrame) -> pd.DataFrame:
    combined = pd.concat([internal, external], ignore_index=True)
    combined["ID_indicateur"] = combined["ID_indicateur"].astype(str).str.strip().str.lower()
    combined = combined.dropna(subset=["ID_indicateur"])
    combined = combined.drop_duplicates(subset=["ID_indicateur"], keep="first")
    return combined


def with_numeric_scores(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["Score"] = df["Score"].apply(to_float)
    df["Coef_ponderation"] = df["Coef_ponderation"].apply(to_float).fillna(1.0)
    df["Exclusion"] = df["Exclusion"].astype(str)
    return df


def build_indicator_csv(df: pd.DataFrame) -> pd.DataFrame:
    expected_ids = [f"i{index:03d}" for index in range(1, 165)]
    output = pd.DataFrame({"indicateur_code": expected_ids})
    merged = output.merge(
        df[["ID_indicateur", "Score"]],
        left_on="indicateur_code",
        right_on="ID_indicateur",
        how="left",
    )
    merged["score"] = merged["Score"].apply(to_int_score)
    return merged[["indicateur_code", "score"]]


def weighted_mean(df: pd.DataFrame) -> float | None:
    if df.empty:
        return None
    scores = df["Score"].astype(float)
    weights = df["Coef_ponderation"].astype(float)
    if weights.sum() == 0:
        return None
    return float((scores * weights).sum() / weights.sum())


def build_aggregated_scores(df: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    mapping_id_col = find_column(mapping.columns, ["ID_indicateurs", "ID_indicateur"])
    if not mapping_id_col:
        raise ValueError("Colonne ID_indicateurs introuvable dans Répartition moyenne.xlsx.")

    mapping = mapping.copy()
    mapping["ID_indicateur"] = mapping[mapping_id_col].astype(str).str.strip().str.lower()

    merged = mapping.merge(df, on="ID_indicateur", how="left")
    merged = merged[~merged["Exclusion"].apply(is_yes)]
    merged = merged[merged["Score"].notna()]

    def membership_mask(column: str) -> pd.Series:
        return merged[column].astype(str).str.strip().str.lower().eq("x")

    output_rows = []

    besoin_columns = {
        "b01": "b01_",
        "b02": "b02_",
        "b03": "b03_",
        "b04": "b04_",
        "b05": "b05_",
        "b06": "b06_",
        "b07": "b07_",
        "b08": "b08_",
        "b09": "b09_",
        "b10": "b10_",
        "b11": "b11_",
    }
    objectif_columns = {
        "Subsistance": "o1_",
        "Gestion de crise": "o2_",
        "Soutenabilité": "o3_",
    }
    type_columns = {
        "État": "typ1_",
        "Action": "typ2_",
    }

    def find_column_by_prefix(prefix: str) -> str | None:
        for col in mapping.columns:
            if normalize_col(col).startswith(normalize_col(prefix)):
                return col
        return None

    for code, prefix in besoin_columns.items():
        col = find_column_by_prefix(prefix)
        group = merged[membership_mask(col)] if col else merged.iloc[0:0]
        score = weighted_mean(group)
        output_rows.append(
            {
                "type": "besoin",
                "code": code,
                "score": to_int_score(score),
            }
        )

    for code, prefix in objectif_columns.items():
        col = find_column_by_prefix(prefix)
        group = merged[membership_mask(col)] if col else merged.iloc[0:0]
        score = weighted_mean(group)
        output_rows.append(
            {
                "type": "objectif",
                "code": code,
                "score": to_int_score(score),
            }
        )

    for code, prefix in type_columns.items():
        col = find_column_by_prefix(prefix)
        group = merged[membership_mask(col)] if col else merged.iloc[0:0]
        score = weighted_mean(group)
        output_rows.append(
            {
                "type": "type_indicateur",
                "code": code,
                "score": to_int_score(score),
            }
        )

    global_score = weighted_mean(merged)
    output_rows.append(
        {
            "type": "global",
            "code": "global",
            "score": to_int_score(global_score),
        }
    )

    return pd.DataFrame(output_rows)


st.set_page_config(page_title="diag_360", layout="wide")

st.markdown(
    """
    <style>
      :root {
        --diag-green: #1f7a4d;
        --diag-green-dark: #0f3d26;
        --diag-green-light: #e8f5ee;
        --diag-green-border: #b7e1c7;
      }
      .diag360-explain {
        background: linear-gradient(135deg, var(--diag-green-light), #f7fffb);
        border: 1px solid var(--diag-green-border);
        padding: 1.2rem 1.4rem;
        border-radius: 16px;
        color: var(--diag-green-dark);
        box-shadow: 0 10px 22px rgba(31, 122, 77, 0.15);
        margin-bottom: 1.5rem;
      }
      .diag360-explain h3 {
        margin: 0 0 0.6rem 0;
        color: var(--diag-green);
        font-size: 1.2rem;
      }
      .diag360-explain ol {
        margin: 0;
        padding-left: 1.2rem;
      }
      .diag360-explain li {
        margin: 0.35rem 0;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("diag_360")
st.markdown(
    """
    <div class="diag360-explain">
      <h3>Mode d'emploi</h3>
      <ol>
        <li>Sélectionnez l'EPCI ciblé dans la liste.</li>
        <li>Chargez votre fichier <strong>epci</strong> (.xlsx).</li>
        <li>Chargez le fichier <strong>coefficients externes</strong> (.xlsx) fourni, basé sur le template.</li>
        <li>Cliquez sur <strong>Calculer</strong> pour générer les deux CSV.</li>
      </ol>
    </div>
    """,
    unsafe_allow_html=True,
)

if not EPCI_PATH.exists():
    st.error("Le fichier epci_membres .csv est introuvable dans le dossier streamlit.")
    st.stop()

if not PARAMS_PATH.exists():
    st.error("Le fichier Parametres_indicateurs.csv est introuvable dans le dossier streamlit.")
    st.stop()

if not EXTERNAL_SCORES_CSV.exists():
    st.error("Le fichier score_indicateurs.csv est introuvable dans le dossier streamlit.")
    st.stop()

if not MAPPING_PATH.exists():
    st.error("Le fichier Répartition_moyenne.csv est introuvable dans le dossier streamlit/source.")
    st.stop()

with st.spinner("Chargement des EPCI..."):
    epcis = load_epci_choices()

epci_lookup = dict(zip(epcis["siren"], epcis["epci_nom"]))
selected_siren = st.selectbox(
    "EPCI",
    options=epcis["siren"].tolist(),
    format_func=lambda code: f"{epci_lookup.get(code, '')}",
)

uploaded_epci = st.file_uploader("Fichier de l'epci(.xlsx)", type=["xlsx"])
uploaded_external_coeffs = st.file_uploader(
    "Fichier coefficients externes (.xlsx)", type=["xlsx"], key="external_coeffs"
)

if st.button(
    "Calculer", disabled=uploaded_epci is None or uploaded_external_coeffs is None
):
    params = load_params()
    mapping = load_mapping()
    external_coeffs = load_external_coeffs()
    external_dataset = load_external_scores_dataset()
    try:
        epci_df = pd.read_excel(uploaded_epci, dtype=str)
        internal_scored = build_scored_internal(epci_df, params)
        internal_scored = with_numeric_scores(internal_scored)

        external_coeffs = load_external_coeffs(uploaded_external_coeffs)
        external_scores = load_external_scores(selected_siren, external_dataset)
        external_table = build_external_table(external_scores, external_coeffs)
        external_table = with_numeric_scores(external_table)

        combined = merge_tables(internal_scored, external_table)
        combined = with_numeric_scores(combined)

        indicator_csv = build_indicator_csv(combined)
        aggregated_csv = build_aggregated_scores(combined, mapping)

        st.success("Calcul terminé.")

        st.subheader("Table fusionnée (aperçu)")
        st.dataframe(combined.head(20))

        st.subheader("CSV indicateurs")
        st.dataframe(indicator_csv.head(20))
        st.download_button(
            "Télécharger csv_indicateurs.csv",
            data=indicator_csv.to_csv(index=False),
            file_name="csv_indicateurs.csv",
            mime="text/csv",
        )

        st.subheader("CSV score agrégé")
        st.dataframe(aggregated_csv)
        st.download_button(
            "Télécharger score_agrege.csv",
            data=aggregated_csv.to_csv(index=False),
            file_name="score_agrege.csv",
            mime="text/csv",
        )
    except Exception as exc:
        st.error(f"Erreur pendant le calcul : {exc}")
