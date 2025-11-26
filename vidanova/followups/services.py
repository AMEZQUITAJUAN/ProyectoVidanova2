import os
import unicodedata
import pandas as pd
import numpy as np
import json
import re
from datetime import date, datetime
from django.db import transaction
from django.conf import settings
from django.db.models import Count, Q
from patients.models import Patient
from .models import FollowUp

# --- 1. UTILIDADES ---

def normalize_text(text):
    if not isinstance(text, str): return str(text) if text is not None else ""
    text = text.strip().lower()
    text = text.replace('\ufeff', '')
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    return text

def normalize_header(text):
    return normalize_text(text).replace(" ", "_").replace(".", "").replace("\n", "")

def limpiar_dato(val):
    if pd.isna(val) or val is None or val == "": return None
    texto = str(val).strip()
    if texto.endswith('.0'): texto = texto[:-2]
    nulos = ['nan', 'nat', 'none', 'null', '0', 'na', '#n/a', 'sin dato']
    if texto.lower() in nulos: return None
    return texto

def parse_date(date_val):
    """
    Convierte fechas eliminando advertencias de Pandas.
    Detecta automáticamente si es YYYY-MM-DD (ISO) o DD/MM/YYYY (Latino).
    """
    if pd.isna(date_val): return None
    
    # Si ya es fecha
    if isinstance(date_val, (datetime, pd.Timestamp)):
        return date_val.date()
    
    s = str(date_val).strip()
    if not s or s.lower() in ['nan', 'nat', '']: return None

    # Limpiar hora si viene (ej: 2025-06-02 00:00:00)
    if " " in s: s = s.split(" ")[0]

    try:
        # 1. Detectar formato ISO (YYYY-MM-DD) usando Regex simple
        # Esto evita la advertencia de 'dayfirst'
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}', s):
            return pd.to_datetime(s).date()
        
        # 2. Si no parece ISO, asumimos Latino (DD/MM/YYYY)
        return pd.to_datetime(s, dayfirst=True).date()
    except:
        return None

# --- 2. LECTURA Y CARGA ---

def leer_archivo_inteligente(file_path):
    try:
        if file_path.endswith('.csv'):
            try:
                df = pd.read_csv(file_path, sep=None, engine='python', dtype=str, encoding='utf-8')
            except:
                df = pd.read_csv(file_path, sep=';', dtype=str, encoding='latin-1')
        else:
            df = pd.read_excel(file_path, dtype=str)
    except Exception as e:
        return None, f"Error archivo: {str(e)}"

    if df is None or df.empty: return None, "Archivo vacío"

    raw_columns = [normalize_header(c) for c in df.columns]
    cols_obligatorias = ['identificacion', 'cedula', 'numero_documento', 'tipo_de_identificacion']
    header_idx = -1
    
    if any(c in raw_columns for c in cols_obligatorias):
        df.columns = raw_columns
    else:
        for i in range(min(15, len(df))):
            fila = df.iloc[i].astype(str).tolist()
            fila_norm = [normalize_header(x) for x in fila]
            if any(c in fila_norm for c in cols_obligatorias):
                header_idx = i
                df.columns = fila_norm
                df = df.iloc[i+1:].reset_index(drop=True)
                break
        if header_idx == -1: df.columns = raw_columns

    df.dropna(how='all', inplace=True)
    return df, None

def importar_archivo_masivo(file_path):
    print("🚀 INICIANDO CARGA (OPTIMIZADA 500/BATCH)...")
    df, error = leer_archivo_inteligente(file_path)
    if error: return {"error": error}

    column_mapping = {
        'numero_documento': ['identificacion', 'cedula', 'numero_documento', 'documento'],
        'tipo_documento': ['tipo_de_identificacion', 'tipo_identificacion'],
        'n1': ['nombre_1', 'primer_nombre'], 'n2': ['nombre_2'], 
        'a1': ['apellido_1', 'primer_apellido'], 'a2': ['apellido_2'],
        'nombre_completo': ['nombre_completo', 'paciente', 'nombres_y_apellidos'],
        'fecha_solicitud_cita': ['fecha_de_solicitud_de_cita', 'fecha_solicitud', 'fecha_radicacion'],
        'fecha_cita': ['fecha_de_cita', 'fecha_cita', 'f_cita'],
        'fecha_captacion': ['fecha_de__captacion', 'fecha_captacion'], 
        'estado_solicitud': ['estado_de_solicitud', 'estado', 'status'],
        'tipo_procedimiento': ['tipo_de_procedimiento', 'procedimiento', 'servicio'],
        'barrera': ['barrera'], 'observaciones': ['observaciones'],
        'entidad_aseguradora': ['entidad_asegurdora', 'entidad_aseguradora', 'eps'],
        'cups': ['cups'], 'ruta': ['ruta']
    }

    rename_dict = {}
    cols_act = df.columns
    for std, aliases in column_mapping.items():
        for alias in aliases:
            if alias in cols_act:
                rename_dict[alias] = std
                break
    df.rename(columns=rename_dict, inplace=True)

    if 'numero_documento' not in df.columns:
        return {"error": "Falta columna Identificación"}

    # 1. PACIENTES
    docs = set(df['numero_documento'].dropna().apply(limpiar_dato).unique())
    docs.discard(None)
    existing_p = Patient.objects.filter(numero_documento__in=docs).values('id', 'numero_documento')
    pmap = {p['numero_documento']: p['id'] for p in existing_p}
    
    new_p = []
    seen_p = set()
    for row in df.itertuples(index=False):
        doc = limpiar_dato(getattr(row, 'numero_documento', None))
        if not doc or doc in pmap or doc in seen_p: continue
        
        n1 = limpiar_dato(getattr(row, 'n1', None))
        a1 = limpiar_dato(getattr(row, 'a1', None))
        full = f"{n1 or ''} {a1 or ''}".strip() or limpiar_dato(getattr(row, 'nombre_completo', None)) or "PACIENTE"
        
        new_p.append(Patient(numero_documento=doc, nombre_1=full.upper()[:99], tipo_documento='CC'))
        seen_p.add(doc)

    if new_p:
        # Batch size reducido para evitar bloqueos
        Patient.objects.bulk_create(new_p, batch_size=500, ignore_conflicts=True)
        existing_p = Patient.objects.filter(numero_documento__in=docs).values('id', 'numero_documento')
        pmap = {p['numero_documento']: p['id'] for p in existing_p}

    # 2. SEGUIMIENTOS
    ids = list(pmap.values())
    existing_f = FollowUp.objects.filter(patient_id__in=ids).values('id', 'patient_id', 'fecha_solicitud_cita', 'tipo_procedimiento')
    
    sig_map = {}
    for f in existing_f:
        d_str = str(f['fecha_solicitud_cita']) if f['fecha_solicitud_cita'] else "SIN_FECHA"
        proc = normalize_text(f['tipo_procedimiento'])
        sig_map[(f['patient_id'], d_str, proc)] = f['id']

    create_list = []
    update_list = []
    
    debug_c = 0

    for row in df.itertuples(index=False):
        doc = limpiar_dato(getattr(row, 'numero_documento', None))
        pid = pmap.get(doc)
        if not pid: continue

        d_sol = parse_date(getattr(row, 'fecha_solicitud_cita', None))
        if not d_sol: d_sol = parse_date(getattr(row, 'fecha_captacion', None))
        d_sol_str = str(d_sol) if d_sol else "SIN_FECHA"

        d_cita = parse_date(getattr(row, 'fecha_cita', None))

        proc_raw = limpiar_dato(getattr(row, 'tipo_procedimiento', None)) or 'CONSULTA'
        proc_norm = normalize_text(proc_raw)

        est_raw = normalize_text(getattr(row, 'estado_solicitud', 'PENDIENTE'))
        estado = 'PENDIENTE'
        if 'realiz' in est_raw or 'efectiv' in est_raw: estado = 'REALIZADO'
        elif 'agen' in est_raw or 'asig' in est_raw: estado = 'AGENDADO'
        elif 'cancel' in est_raw or 'no pgp' in est_raw: estado = 'CANCELADO'
        elif 'gest' in est_raw: estado = 'EN_GESTION'

        if debug_c < 1: # Solo imprimir 1 para verificar
            print(f"🕵️ DEBUG: Doc={doc} | Sol={d_sol_str} | Est={estado}")
            debug_c += 1

        sig = (pid, d_sol_str, proc_norm)

        if sig in sig_map:
            fid = sig_map[sig]
            if fid != -1: 
                f = FollowUp(id=fid)
                f.estado_solicitud = estado
                f.fecha_cita = d_cita
                f.barrera = limpiar_dato(getattr(row, 'barrera', None))
                f.observaciones = limpiar_dato(getattr(row, 'observaciones', None))
                f.ruta = limpiar_dato(getattr(row, 'ruta', None))
                f.entidad_aseguradora = limpiar_dato(getattr(row, 'entidad_aseguradora', None))
                update_list.append(f)
        else:
            new_f = FollowUp(
                patient_id=pid,
                tipo_procedimiento=proc_raw.upper(),
                fecha_solicitud_cita=d_sol,
                estado_solicitud=estado,
                fecha_cita=d_cita,
                barrera=limpiar_dato(getattr(row, 'barrera', None)),
                observaciones=limpiar_dato(getattr(row, 'observaciones', None)),
                ruta=limpiar_dato(getattr(row, 'ruta', None)),
                entidad_aseguradora=limpiar_dato(getattr(row, 'entidad_aseguradora', None)),
                cups=limpiar_dato(getattr(row, 'cups', None))
            )
            create_list.append(new_f)
            sig_map[sig] = -1 

    with transaction.atomic():
        # BATCH SIZE 500 (La clave para evitar Database Locked)
        if create_list: FollowUp.objects.bulk_create(create_list, batch_size=500)
        if update_list: 
            FollowUp.objects.bulk_update(update_list, 
                ['estado_solicitud', 'fecha_cita', 'barrera', 'observaciones', 'ruta', 'entidad_aseguradora'], 
                batch_size=500)

    print(f"✅ FIN: {len(create_list)} Creados, {len(update_list)} Actualizados")
    return {"success": True, "registros": len(create_list), "actualizados": len(update_list)}

# --- 3. MÉTRICAS (Mismas que antes) ---

def compute_request_status_from_db(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    active = queryset.exclude(estado_solicitud__icontains='CANCELADO')
    total = active.count()
    if total == 0: return {"labels": ["Sin Datos"], "values": [0], "completados": 0, "pendientes": 0, "porcentaje_completado": 0}
    
    realizados = active.filter(estado_solicitud__icontains='REALIZADO').count()
    agendados = active.filter(estado_solicitud__icontains='AGENDADO').count()
    pendientes = active.filter(Q(estado_solicitud__icontains='PENDIENTE') | Q(estado_solicitud__icontains='GESTION')).count()
    
    return {
        "labels": ["Realizado", "Agendado", "Pendiente"],
        "values": [realizados, agendados, pendientes],
        "completados": realizados,
        "pendientes": pendientes + agendados,
        "porcentaje_completado": round((realizados/total)*100, 1)
    }

def compute_barriers(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    data = queryset.exclude(Q(barrera__isnull=True)|Q(barrera__exact='')).values('barrera').annotate(total=Count('id')).order_by('-total')[:5]
    return {"labels": [x['barrera'] for x in data], "values": [x['total'] for x in data]}

def compute_opportunity_by_procedure(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    data = queryset.values('tipo_procedimiento').annotate(total=Count('id')).order_by('-total')[:10]
    labels = [str(x['tipo_procedimiento'])[:20]+"..." for x in data]
    return {"procedimiento_labels": json.dumps(labels), "values": [x['total'] for x in data]}

def compute_institutional_metrics_db():
    return {'gender_labels': '[]', 'gender_values': '[]'}