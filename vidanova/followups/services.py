import os
import unicodedata
import pandas as pd
from django.conf import settings

def normalize_columns(cols):
    def clean(c):
        c = str(c).strip().lower()
        c = unicodedata.normalize('NFKD', c).encode('ascii', 'ignore').decode('utf-8')
        c = c.replace(" ", "_").replace("__", "_")
        return c
    return [clean(x) for x in cols]

def save_processed_dataframe(df, filename="processed_latest.csv"):
    uploads_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    processed_path = os.path.join(uploads_dir, filename)
    df.to_csv(processed_path, index=False, encoding='utf-8-sig')
    return processed_path

def read_any_dataframe(path):
    if path.endswith(".xlsx"):
        return pd.read_excel(path)
    if path.endswith(".csv"):
        return pd.read_csv(path)
    raise ValueError("Formato no soportado. Usa .csv o .xlsx")

def load_dashboard_dataframe():
    csv_path = os.path.join(settings.MEDIA_ROOT, "uploads", "processed_latest.csv")
    if not os.path.exists(csv_path):
        return None, csv_path
    df = pd.read_csv(csv_path)
    df.columns = normalize_columns(df.columns)
    return df, csv_path

def compute_institutional_metrics(df: pd.DataFrame):
    # Maneja ausencias de columnas con defaults seguros
    out = {}

    # Grupo diagnóstico (top 10)
    if "grupo_diagnostico" in df.columns:
        diag_data = df["grupo_diagnostico"].value_counts().head(10)
        out["diag_labels"] = diag_data.index.tolist()
        out["diag_values"] = diag_data.values.tolist()
    else:
        out["diag_labels"], out["diag_values"] = [], []

    # Género
    if "genero" in df.columns:
        g = df["genero"].value_counts()
        out["gender_labels"] = g.index.tolist()
        out["gender_values"] = g.values.tolist()
    else:
        out["gender_labels"], out["gender_values"] = [], []

    # Edad agrupada
    if "edad" in df.columns:
        df["edad"] = pd.to_numeric(df["edad"], errors="coerce")
        bins = [0, 20, 30, 40, 50, 60, 70, 80, 120]
        labels = ["<20", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]
        df["rango_edad"] = pd.cut(df["edad"], bins=bins, labels=labels, right=False)
        age_data = df["rango_edad"].value_counts().sort_index()
        out["age_labels"] = age_data.index.tolist()
        out["age_values"] = age_data.values.tolist()
    else:
        out["age_labels"], out["age_values"] = [], []

    # Estado solicitud
    for col in ("estado_de_solicitud", "estado_de__solicitud"):
        if col in df.columns:
            s = df[col].value_counts()
            out["state_labels"] = s.index.tolist()
            out["state_values"] = s.values.tolist()
            break
    else:
        out["state_labels"], out["state_values"] = [], []

    # Oportunidad (promedio)
    if "oportunidad" in df.columns:
        df["oportunidad_num"] = pd.to_numeric(df["oportunidad"], errors="coerce")
        out["oportunidad_promedio"] = round(df["oportunidad_num"].mean(skipna=True), 2)
    else:
        out["oportunidad_promedio"] = None

    # Mes de ordenamiento
    if "mes_de_ordenamiento" in df.columns:
        month_data = df["mes_de_ordenamiento"].value_counts()
        out["month_labels"] = month_data.index.tolist()
        out["month_values"] = month_data.values.tolist()
    else:
        out["month_labels"], out["month_values"] = [], []

    # Puedes reutilizar month_* para otras gráficas simples
    out["cnt_labels"] = out["month_labels"]
    out["cnt_values"] = out["month_values"]

    return out