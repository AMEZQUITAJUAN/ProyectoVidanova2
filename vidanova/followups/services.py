import os
import unicodedata
import pandas as pd
import numpy as np
import json
from django.db import transaction
from django.conf import settings
from django.db.models import Count, Q
from patients.models import Patient
from treatments.models import Treatment
from .models import FollowUp  # Importamos el modelo, NO lo definimos aquí
from django.db.models.functions import TruncMonth
from django.db.models import Avg, F, ExpressionWrapper, fields

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
    out = {}
    # Grupo diagnóstico
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

    # Estado solicitud (CSV)
    for col in ("estado_de_solicitud", "estado_de__solicitud"):
        if col in df.columns:
            s = df[col].value_counts()
            out["state_labels"] = s.index.tolist()
            out["state_values"] = [int(v) for v in s.values.tolist()]
            break
    else:
        out["state_labels"], out["state_values"] = [], []

    # Oportunidad
    if "oportunidad" in df.columns:
        df["oportunidad_num"] = pd.to_numeric(df["oportunidad"], errors="coerce")
        out["oportunidad_promedio"] = round(df["oportunidad_num"].mean(skipna=True), 2)
    else:
        out["oportunidad_promedio"] = None

    return out

def compute_request_status_from_db(queryset=None):
    """
    Calcula los contadores de estado basándose en los Choices del modelo.
    """
    if queryset is None:
        queryset = FollowUp.objects.all()

    ESTADOS_REALIZADO = ['REALIZADO']
    ESTADOS_AGENDADO = ['AGENDADO']
    ESTADOS_PENDIENTE = ['PENDIENTE', 'EN_GESTION', 'POR_GESTIONAR', 'NO_AUTORIZADO']
    ESTADOS_CANCELADO = ['CANCELADO']

    active_qs = queryset.exclude(estado_solicitud__in=ESTADOS_CANCELADO)
    total = active_qs.count()

    if total == 0:
        return {
            "labels": ["Realizado", "Agendado", "Pendiente"],
            "values": [0, 0, 0],
            "completados": 0,
            "pendientes": 0,
            "porcentaje_completado": 0,
        }

    completados = active_qs.filter(estado_solicitud__in=ESTADOS_REALIZADO).count()
    agendados = active_qs.filter(estado_solicitud__in=ESTADOS_AGENDADO).count()
    pendientes = active_qs.filter(estado_solicitud__in=ESTADOS_PENDIENTE).count()
    
    porcentaje = round((completados / total) * 100, 1)

    return {
        "labels": ["Realizado", "Agendado", "Pendiente"],
        "values": [completados, agendados, pendientes],
        "completados": completados,
        "pendientes": pendientes + agendados,
        "porcentaje_completado": porcentaje,
    }

def compute_opportunity_by_procedure(queryset=None):
    """
    Cuenta cuántas solicitudes hay por tipo de procedimiento.
    """
    if queryset is None:
        queryset = FollowUp.objects.all()

    data = queryset.values('tipo_procedimiento')\
        .annotate(total=Count('id'))\
        .order_by('-total')[:10]

    labels = [item['tipo_procedimiento'] for item in data]
    values = [item['total'] for item in data]

    return {
        "procedimiento_labels": labels,
        "values": values,
    }
def importar_archivo_masivo(file_path):
    """
    Lee Excel/CSV, normaliza columnas, busca pacientes y crea registros masivamente.
    """
    # 1. Leer archivo (detecta si es Excel o CSV)
    if file_path.endswith('.csv'):
        df = pd.read_csv(file_path)
    else:
        df = pd.read_excel(file_path)

    # 2. DICCIONARIO DE SINÓNIMOS (El cerebro de la interpretación)
    # Mapea posibles nombres incorrectos al nombre real de tu BD
    column_mapping = {
        # Nombre en BD : [Lista de posibles nombres en el Excel]
        'documento': ['cedula', 'id', 'identificacion', 'doc_identidad', 'documento'],
        'nombre': ['paciente', 'nombre_completo', 'nombres', 'usuario'],
        'fecha_solicitud_cita': ['fecha_solicitud', 'f_solicitud', 'fecha_orden', 'fecha_recepcion'],
        'tipo_procedimiento': ['procedimiento', 'tipo_servicio', 'servicio_solicitado'],
        'estado_solicitud': ['estado', 'status', 'estado_actual'],
        'fecha_cita': ['fecha_asignada', 'f_cita', 'fecha_agenda'],
        'observaciones': ['obs', 'comentario', 'nota']
    }

    # Normalizar columnas del DataFrame
    df.columns = [c.lower().strip() for c in df.columns] # Todo a minúsculas
    
    # Renombrar columnas según el mapa
    rename_dict = {}
    for real_col, aliases in column_mapping.items():
        for alias in aliases:
            if alias in df.columns:
                rename_dict[alias] = real_col
                break # Encontró una coincidencia
    
    df.rename(columns=rename_dict, inplace=True)

    # 3. Validaciones Mínimas
    if 'documento' not in df.columns:
        return {"error": "No se encontró columna de Documento/Cédula"}

    # 4. Preparar Datos para Inserción Masiva (Bulk Create)
    followups_to_create = []
    
    # Cachear pacientes existentes para no consultar DB mil veces
    # Traemos todos los documentos y sus IDs en un diccionario {doc: id}
    existing_patients = dict(Patient.objects.values_list('documento', 'id'))
    patients_to_create = []

    # Primera pasada: Identificar pacientes nuevos
    # (Pandas es 100 veces más rápido que un for de Python)
    unique_docs = df['documento'].unique()
    for doc in unique_docs:
        doc_str = str(doc).strip()
        if doc_str not in existing_patients:
            # Si no existe, lo preparamos para crear
            # Intenta buscar el nombre en la fila correspondiente
            row = df[df['documento'] == doc].iloc[0]
            nombre_paciente = row.get('nombre', 'Paciente Nuevo Importado')
            patients_to_create.append(Patient(documento=doc_str, nombre=nombre_paciente))

    # Crear pacientes nuevos en bloque
    if patients_to_create:
        Patient.objects.bulk_create(patients_to_create)
        # Actualizar caché
        existing_patients = dict(Patient.objects.values_list('documento', 'id'))
# ... (esto va después de crear los pacientes)
    # 4.5 PREVENIR DUPLICADOS (La clave anti-lag)
    # Creamos una "huella digital" de lo que ya existe en BD para no repetirlo.
    # Clave única: ID Paciente + Fecha Solicitud + Tipo Procedimiento
    existing_signatures = set(
        FollowUp.objects.values_list('patient_id', 'fecha_solicitud_cita', 'tipo_procedimiento')
    )

    # Segunda pasada: Crear los Seguimientos
    for index, row in df.iterrows():
        doc_str = str(row['documento']).strip()
        patient_id = existing_patients.get(doc_str)

        if not patient_id:
            continue 

        # Limpieza y Mapeo (Igual que antes)
        estado_raw = str(row.get('estado_solicitud', 'PENDIENTE')).upper()
        # ... (toda tu lógica de mapeo de ESTADOS aquí) ...
        estado_final = 'PENDIENTE'
        if 'REALIZ' in estado_raw: estado_final = 'REALIZADO'
        elif 'AGEN' in estado_raw: estado_final = 'AGENDADO'
        elif 'GEST' in estado_raw: estado_final = 'EN_GESTION'
        elif 'CANCEL' in estado_raw: estado_final = 'CANCELADO'

        # ... (toda tu lógica de mapeo de PROCEDIMIENTOS aquí) ...
        proc_raw = str(row.get('tipo_procedimiento', 'CONSULTA')).upper()
        proc_final = 'CONSULTA'
        if 'CIRU' in proc_raw: proc_final = 'CIRUGIA'
        elif 'QUIM' in proc_raw: proc_final = 'QUIMIOTERAPIA'
        elif 'RADIO' in proc_raw: proc_final = 'RADIOTERAPIA'
        elif 'IMAG' in proc_raw: proc_final = 'IMAGENES'
        elif 'LAB' in proc_raw: proc_final = 'LABORATORIO'
        elif 'PATO' in proc_raw: proc_final = 'PATOLOGIA'

        # Fechas
        f_sol = pd.to_datetime(row.get('fecha_solicitud_cita'), errors='coerce')
        f_cita = pd.to_datetime(row.get('fecha_cita'), errors='coerce')
        
        date_sol_obj = f_sol.date() if not pd.isnull(f_sol) else None
        date_cita_obj = f_cita.date() if not pd.isnull(f_cita) else None

        # --- EL FILTRO MÁGICO ---
        # Si esta combinación ya existe, SALTAMOS (continue). No creamos basura.
        signature = (patient_id, date_sol_obj, proc_final)
        if signature in existing_signatures:
            continue
            
        # Si es nuevo, lo agregamos a la lista y actualizamos la firma para no repetirlo en este mismo archivo
        existing_signatures.add(signature)

        followups_to_create.append(FollowUp(
            patient_id=patient_id,
            tipo_procedimiento=proc_final,
            estado_solicitud=estado_final,
            fecha_solicitud_cita=date_sol_obj,
            fecha_cita=date_cita_obj,
            observaciones=row.get('observaciones', '')
        ))

    # 5. Insertar (Solo lo nuevo)
    if followups_to_create:
        with transaction.atomic():
            FollowUp.objects.bulk_create(followups_to_create, batch_size=2000)
        return {"success": True, "registros": len(followups_to_create), "mensaje": "Carga exitosa"}
    else:
        return {"success": True, "registros": 0, "mensaje": "No se encontraron registros nuevos (todo estaba duplicado)"}
def compute_barriers(queryset=None):
    """
    Calcula el top de barreras más frecuentes.
    Excluye 'NINGUNA' para mostrar solo problemas reales.
    """
    if queryset is None:
        queryset = FollowUp.objects.all()

    # Filtramos 'NINGUNA' y 'None' para ver solo obstáculos reales
    # Agrupamos por el campo 'barrera' y contamos
    data = queryset.exclude(Q(barrera='NINGUNA') | Q(barrera__isnull=True) | Q(barrera='')) \
                   .values('barrera') \
                   .annotate(total=Count('id')) \
                   .order_by('-total')[:5] # Top 5 barreras

    labels = [item['barrera'] for item in data]
    values = [item['total'] for item in data]

    return {
        "labels": labels,
        "values": values,
    }
def compute_institutional_metrics_db():
    """
    Calcula métricas demográficas y operativas directamente de la Base de Datos.
    """
    # 1. GÉNERO (Desde modelo Patient)
    # Asume que el campo se llama 'genero' en Patient
    gender_qs = Patient.objects.values('genero').annotate(total=Count('id')).order_by('-total')
    gender_labels = [x['genero'] or 'Sin Registro' for x in gender_qs]
    gender_values = [x['total'] for x in gender_qs]

    # 2. EDAD (Calculado en Python para facilitar rangos)
    # Traemos todas las edades y las agrupamos
    edades = Patient.objects.values_list('edad', flat=True)
    buckets = {'0-18': 0, '19-30': 0, '31-50': 0, '51-70': 0, '71+': 0, 'N/A': 0}
    
    for edad in edades:
        if edad is None:
            buckets['N/A'] += 1
        elif edad <= 18:
            buckets['0-18'] += 1
        elif edad <= 30:
            buckets['19-30'] += 1
        elif edad <= 50:
            buckets['31-50'] += 1
        elif edad <= 70:
            buckets['51-70'] += 1
        else:
            buckets['71+'] += 1
            
    age_labels = list(buckets.keys())
    age_values = list(buckets.values())

    # 3. PROCEDIMIENTOS (Reemplaza a Diagnóstico)
    proc_qs = FollowUp.objects.values('tipo_procedimiento').annotate(total=Count('id')).order_by('-total')[:8]
    diag_labels = [x['tipo_procedimiento'] for x in proc_qs]
    diag_values = [x['total'] for x in proc_qs]

    # 4. ESTADO SOLICITUD
    status_qs = FollowUp.objects.values('estado_solicitud').annotate(total=Count('id'))
    state_labels = [x['estado_solicitud'] for x in status_qs]
    state_values = [x['total'] for x in status_qs]

    # 5. COMPORTAMIENTO MENSUAL (Línea de tiempo)
    # Agrupa por mes de la fecha de solicitud
    monthly_qs = FollowUp.objects.annotate(
        mes=TruncMonth('fecha_solicitud_cita')
    ).values('mes').annotate(total=Count('id')).order_by('mes')

    # Formateamos fecha "Ene 2024"
    month_labels = [x['mes'].strftime('%b %Y') if x['mes'] else 'S/F' for x in monthly_qs]
    count_values = [x['total'] for x in monthly_qs]

    return {
        'gender_labels': json.dumps(gender_labels),
        'gender_values': json.dumps(gender_values),
        'age_labels': json.dumps(age_labels),
        'age_values': json.dumps(age_values),
        'diag_labels': json.dumps(diag_labels),
        'diag_values': json.dumps(diag_values),
        'state_labels': json.dumps(state_labels),
        'state_values': json.dumps(state_values),
        'month_labels': json.dumps(month_labels),
        'cnt_values': json.dumps(count_values),
        # Reutilizamos las etiquetas de mes para oportunidad
        'month_values': json.dumps([]) # Oportunidad compleja de calcular por mes, dejamos vacía por ahora
    }