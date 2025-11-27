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
from django.db.models.functions import TruncMonth
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
    if pd.isna(date_val): return None
    if isinstance(date_val, (datetime, pd.Timestamp)): return date_val.date()
    s = str(date_val).strip()
    if not s or s.lower() in ['nan', 'nat', '']: return None
    if " " in s: s = s.split(" ")[0]
    try:
        if re.match(r'^\d{4}-\d{1,2}-\d{1,2}', s): return pd.to_datetime(s).date()
        return pd.to_datetime(s, dayfirst=True).date()
    except: return None

# --- 2. LECTURA Y CARGA ---

def leer_archivo_inteligente(file_path):
    try:
        if file_path.endswith('.csv'):
            try: df = pd.read_csv(file_path, sep=None, engine='python', dtype=str, encoding='utf-8')
            except: df = pd.read_csv(file_path, sep=';', dtype=str, encoding='latin-1')
        else: df = pd.read_excel(file_path, dtype=str)
    except Exception as e: return None, f"Error archivo: {str(e)}"

    if df is None or df.empty: return None, "Archivo vacío"

    raw_columns = [normalize_header(c) for c in df.columns]
    cols_obligatorias = ['identificacion', 'cedula', 'numero_documento', 'tipo_de_identificacion']
    header_idx = -1
    
    if any(c in raw_columns for c in cols_obligatorias): df.columns = raw_columns
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
    df, error = leer_archivo_inteligente(file_path)
    if error: return {"error": error}

    column_mapping = {
        'numero_documento': ['identificacion', 'cedula', 'numero_documento', 'documento'],
        'tipo_documento': ['tipo_de_identificacion', 'tipo_identificacion'],
        
        # --- LECTURA EXPLÍCITA DE NOMBRES ---
        'n1': ['nombre_1', 'primer_nombre'], 
        'n2': ['nombre_2', 'segundo_nombre'], 
        'a1': ['apellido_1', 'primer_apellido'], 
        'a2': ['apellido_2', 'segundo_apellido'],
        
        'nombre_completo': ['nombre_completo', 'paciente', 'nombres_y_apellidos'],
        'genero': ['genero', 'sexo'], 'edad': ['edad'],
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

    if 'numero_documento' not in df.columns: return {"error": "Falta columna Identificación"}

    # 1. PACIENTES
    docs = set(df['numero_documento'].dropna().apply(limpiar_dato).unique())
    docs.discard(None)
    existing_p = Patient.objects.filter(numero_documento__in=docs).values('id', 'numero_documento')
    pmap = {p['numero_documento']: p['id'] for p in existing_p}
    
    new_p_objs = []
    update_p_objs = []
    processed_docs = set()

    for row in df.itertuples(index=False):
        doc = limpiar_dato(getattr(row, 'numero_documento', None))
        if not doc or doc in processed_docs: continue
        
        gen = limpiar_dato(getattr(row, 'genero', None))
        try: edad = int(float(getattr(row, 'edad', 0)))
        except: edad = None
        
        # --- LOGICA CORREGIDA DE NOMBRES ---
        # Leemos cada columna por separado
        n1 = limpiar_dato(getattr(row, 'n1', None))
        n2 = limpiar_dato(getattr(row, 'n2', None))
        a1 = limpiar_dato(getattr(row, 'a1', None))
        a2 = limpiar_dato(getattr(row, 'a2', None))
        
        # Fallback: Si no hay columnas separadas, buscamos nombre completo
        full_backup = limpiar_dato(getattr(row, 'nombre_completo', None))
        
        # Asignación final (Si n1 está vacío, usamos el full_backup como parche)
        final_n1 = n1 if n1 else (full_backup if full_backup else "PACIENTE")
        final_n2 = n2
        final_a1 = a1 if a1 else "" 
        final_a2 = a2

        if doc in pmap:
            # ACTUALIZAR: Forzamos la actualización de nombres
            p = Patient(id=pmap[doc])
            p.nombre_1 = final_n1.upper()[:99]
            p.nombre_2 = final_n2.upper()[:99] if final_n2 else None
            p.apellido_1 = final_a1.upper()[:99]
            p.apellido_2 = final_a2.upper()[:99] if final_a2 else None
            p.genero = gen
            p.edad = edad
            update_p_objs.append(p)
        else:
            # CREAR
            new_p_objs.append(Patient(
                numero_documento=doc, nombre_1=final_n1.upper()[:99], 
                nombre_2=final_n2.upper()[:99] if final_n2 else None,
                apellido_1=final_a1.upper()[:99],
                apellido_2=final_a2.upper()[:99] if final_a2 else None,
                tipo_documento='CC', genero=gen, edad=edad
            ))
        
        processed_docs.add(doc)

    if new_p_objs:
        Patient.objects.bulk_create(new_p_objs, batch_size=500, ignore_conflicts=True)
        # Recargar mapa
        existing_p = Patient.objects.filter(numero_documento__in=docs).values('id', 'numero_documento')
        pmap = {p['numero_documento']: p['id'] for p in existing_p}
    
    if update_p_objs:
        # AQUÍ ESTABA EL ERROR: Ahora incluimos los nombres en la actualización
        Patient.objects.bulk_update(
            update_p_objs, 
            ['nombre_1', 'nombre_2', 'apellido_1', 'apellido_2', 'genero', 'edad'], 
            batch_size=500
        )

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

        sig = (pid, d_sol_str, proc_norm)
        
        barrera = limpiar_dato(getattr(row, 'barrera', None))
        obs = limpiar_dato(getattr(row, 'observaciones', None))
        ruta = limpiar_dato(getattr(row, 'ruta', None))
        eps = limpiar_dato(getattr(row, 'entidad_aseguradora', None))
        cups = limpiar_dato(getattr(row, 'cups', None))

        if sig in sig_map:
            fid = sig_map[sig]
            if fid != -1: 
                f = FollowUp(id=fid)
                f.estado_solicitud = estado
                f.fecha_cita = d_cita
                f.barrera = barrera
                f.observaciones = obs
                f.ruta = ruta
                f.entidad_aseguradora = eps
                update_list.append(f)
        else:
            new_f = FollowUp(
                patient_id=pid, tipo_procedimiento=proc_raw.upper(),
                fecha_solicitud_cita=d_sol, estado_solicitud=estado,
                fecha_cita=d_cita, barrera=barrera, observaciones=obs,
                ruta=ruta, entidad_aseguradora=eps, cups=cups
            )
            create_list.append(new_f)
            sig_map[sig] = -1 

    with transaction.atomic():
        if create_list: FollowUp.objects.bulk_create(create_list, batch_size=500)
        if update_list: 
            FollowUp.objects.bulk_update(update_list, 
                ['estado_solicitud', 'fecha_cita', 'barrera', 'observaciones', 'ruta', 'entidad_aseguradora'], 
                batch_size=500)

    return {"success": True, "registros": len(create_list), "actualizados": len(update_list)}

# --- 3. MÉTRICAS OPERATIVAS (RESTITUÍDAS) ---

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

# --- 4. MÉTRICAS ANALÍTICAS (NUEVAS) ---

def compute_institutional_metrics_db():
    # 1. GÉNERO
    gender_qs = Patient.objects.values('genero').annotate(total=Count('id')).order_by('-total')
    g_labels = [x['genero'] or 'SIN DATO' for x in gender_qs]
    g_values = [x['total'] for x in gender_qs]

    # 2. EDAD
    edades = list(Patient.objects.filter(edad__isnull=False).values_list('edad', flat=True))
    rangos = {'0-18': 0, '19-30': 0, '31-50': 0, '51-70': 0, '71+': 0}
    for e in edades:
        try:
            val = int(e)
            if val <= 18: rangos['0-18'] += 1
            elif val <= 30: rangos['19-30'] += 1
            elif val <= 50: rangos['31-50'] += 1
            elif val <= 70: rangos['51-70'] += 1
            else: rangos['71+'] += 1
        except: pass
    
    a_labels = list(rangos.keys())
    a_values = list(rangos.values())

    # 3. ESTADOS
    status_qs = FollowUp.objects.values('estado_solicitud').annotate(total=Count('id')).order_by('-total')
    s_labels = [str(x['estado_solicitud']).upper() for x in status_qs]
    s_values = [x['total'] for x in status_qs]

    # 4. PROCEDIMIENTOS (Agrupación Inclusiva)
    raw_procs = FollowUp.objects.values_list('tipo_procedimiento', flat=True)
    proc_counts = {}
    
    for p in raw_procs:
        if not p: continue
        p_upper = str(p).upper().strip()
        
        # Lógica de Agrupación
        key = p_upper # Por defecto usamos el nombre original
        
        if 'CONSULTA' in p_upper or 'VALORACION' in p_upper: key = 'CONSULTAS'
        elif 'RESONANCIA' in p_upper or 'TAC' in p_upper or 'ECOGRAFIA' in p_upper or 'RX' in p_upper or 'IMAGEN' in p_upper or 'GAMMAGRAFIA' in p_upper: key = 'IMAGENES DX'
        elif 'LABORATORIO' in p_upper or 'SANGRE' in p_upper or 'HEMOGRAMA' in p_upper or 'PERFIL' in p_upper: key = 'LABORATORIO'
        elif 'QUIMIO' in p_upper or 'APLICACION' in p_upper: key = 'QUIMIOTERAPIA'
        elif 'RADIO' in p_upper: key = 'RADIOTERAPIA'
        elif 'CIRUGIA' in p_upper or 'RESECCION' in p_upper: key = 'CIRUGIA'
        elif 'PATOLOGIA' in p_upper or 'BIOPSIA' in p_upper: key = 'PATOLOGIA'
        
        # Si no coincidió con nada, se guarda como estaba (ej: "INSUMOS")
        proc_counts[key] = proc_counts.get(key, 0) + 1
    
    # Ordenar Top 10
    sorted_procs = sorted(proc_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    d_labels = [x[0] for x in sorted_procs]
    d_values = [x[1] for x in sorted_procs]

    # 5. MENSUAL
    month_qs = FollowUp.objects.annotate(month=TruncMonth('fecha_solicitud_cita'))\
        .values('month').annotate(total=Count('id')).order_by('month')
    m_labels = []
    m_values = []
    for x in month_qs:
        if x['month']:
            m_labels.append(x['month'].strftime('%b %Y'))
            m_values.append(x['total'])

    return {
        'gender_labels': json.dumps(g_labels), 'gender_values': json.dumps(g_values),
        'age_labels': json.dumps(a_labels), 'age_values': json.dumps(a_values),
        'state_labels': json.dumps(s_labels), 'state_values': json.dumps(s_values),
        'diag_labels': json.dumps(d_labels), 'diag_values': json.dumps(d_values),
        'month_labels': json.dumps(m_labels), 'cnt_values': json.dumps(m_values),
    }