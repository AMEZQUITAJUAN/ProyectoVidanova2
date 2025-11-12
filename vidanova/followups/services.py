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
        out["diag_values"] = [int(v) for v in diag_data.values.tolist()]
    else:
        out["diag_labels"], out["diag_values"] = [], []

    # Género
    if "genero" in df.columns:
        g = df["genero"].value_counts()
        out["gender_labels"] = g.index.tolist()
        out["gender_values"] = [int(v) for v in g.values.tolist()]
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
        out["age_values"] = [int(v) for v in age_data.values.tolist()]
    else:
        out["age_labels"], out["age_values"] = [], []

    # Estado solicitud
    for col in ("estado_de_solicitud", "estado_de__solicitud"):
        if col in df.columns:
            s = df[col].value_counts()
            out["state_labels"] = s.index.tolist()
            out["state_values"] = [int(v) for v in s.values.tolist()]
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
        out["month_values"] = [int(v) for v in month_data.values.tolist()]
    else:
        out["month_labels"], out["month_values"] = [], []

    # Puedes reutilizar month_* para otras gráficas simples
    out["cnt_labels"] = out["month_labels"]
    out["cnt_values"] = out["month_values"]

    return out


def compute_request_status_from_db():
    """
    Calcula el estado de solicitud desde la BD (FollowUp).
    Retorna diccionario con etiquetas y valores para gráfico pastel.
    
    Estados:
    - Realizados: completed=True
    - Pendientes: completed=False, interruption_reason vacío
    - Agendados: completed=False, interruption_reason='agendado'
    - En gestión: completed=False, interruption_reason='en_gestion'
    - Por gestionar: completed=False, interruption_reason='por_gestionar'
    """
    from .models import FollowUp
    
    # Contar cada estado (conversión a int para JSON)
    realizados = int(FollowUp.objects.filter(completed=True).count())
    agendados = int(FollowUp.objects.filter(completed=False, interruption_reason='agendado').count())
    en_gestion = int(FollowUp.objects.filter(completed=False, interruption_reason='en_gestion').count())
    por_gestionar = int(FollowUp.objects.filter(completed=False, interruption_reason='por_gestionar').count())
    pendientes = int(FollowUp.objects.filter(completed=False, interruption_reason__in=['', None]).count())
    
    return {
        "estado_labels": ["Realizados", "Agendados", "Pendientes", "En Gestión", "Por Gestionar"],
        "estado_values": [realizados, agendados, pendientes, en_gestion, por_gestionar]
    }


def compute_opportunity_by_procedure():
    """
    Calcula la "Oportunidad por procedimiento" desde la BD (Treatment).
    Retorna diccionario con etiquetas (tipos de procedimiento) y valores (conteos).

    Procedimientos esperados:
    - Oncología
    - Cirugía
    - Radioterapia
    - Quimioterapia
    - Consulta
    - Laboratorio
    - Patología
    - Procedimiento
    - CUPS (código)
    """
    from treatments.models import Treatment
    from patients.models import Patient

    # Etiquetas que queremos mostrar
    labels = ['Oncología', 'Cirugía', 'Radioterapia', 'Quimioterapia', 'Consulta', 'Laboratorio', 'Patología', 'Procedimiento', 'CUPS']
    counts = {k: 0 for k in labels}

    # Contar desde Treatment (tipos conocidos)
    try:
        counts['Quimioterapia'] = int(Treatment.objects.filter(tipo__iexact='QMT').count())
        counts['Radioterapia'] = int(Treatment.objects.filter(tipo__iexact='RX').count())
        counts['Cirugía'] = int(Treatment.objects.filter(tipo__iexact='CIR').count())
    except Exception:
        # Si hay problemas con el ORM, dejamos valores en 0
        pass

    # Contar pacientes con tipo_cancer que contenga 'onc' -> Oncología aproximada
    try:
        counts['Oncología'] = int(Patient.objects.filter(tipo_cancer__icontains='onc').count())
    except Exception:
        pass

    # Intentar enriquecer desde el CSV procesado para consultas, laboratorio, patología, procedimiento y CUPS
    csv_path = os.path.join(settings.MEDIA_ROOT, 'uploads', 'processed_latest.csv')
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            df.columns = normalize_columns(df.columns)

            # columnas candidatas donde puede aparecer el procedimiento o servicio
            candidate_cols = [c for c in df.columns if any(x in c for x in ('proced', 'servic', 'cups', 'servicio', 'procedimiento'))]
            # Para cada label, sumar filas cuyo valor contenga la palabra (heurística)
            for label in ['Consulta', 'Laboratorio', 'Patología', 'Procedimiento', 'CUPS']:
                total = 0
                low = label.lower()
                for col in candidate_cols:
                    try:
                        vals = df[col].astype(str).str.lower()
                        total += int(vals.str.contains(low, na=False).sum())
                    except Exception:
                        continue
                counts[label] = total
        except Exception:
            # Si lectura falla, seguimos con los datos que tenemos
            pass

    return {
        "procedimiento_labels": labels,
        "procedimiento_values": [int(counts[l]) for l in labels]
    }
