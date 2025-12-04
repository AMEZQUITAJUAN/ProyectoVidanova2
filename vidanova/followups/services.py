import os
import unicodedata
import pandas as pd
import numpy as np
import json
import re
import warnings
from datetime import date, datetime
from django.db import transaction
from django.conf import settings
from django.db.models import Count, Q
from django.db.models.functions import TruncMonth
from patients.models import Patient
from .models import FollowUp

# --- 1. UTILIDADES ---

def normalize_text(text):
    """Limpia tildes y caracteres raros de cualquier texto."""
    if not isinstance(text, str): return str(text) if text is not None else ""
    text = text.strip().lower()
    text = text.replace('\ufeff', '')
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    return text

def normalize_header(text):
    """Normaliza nombres de columnas (quita espacios, puntos, etc)."""
    clean = normalize_text(text)
    clean = re.sub(r'[^a-z0-9]', '_', clean)
    clean = re.sub(r'_+', '_', clean)
    return clean.strip('_')

def limpiar_dato(val):
    if pd.isna(val) or val is None or val == "": return None
    texto = str(val).strip()
    if texto.endswith('.0'): texto = texto[:-2]
    nulos = ['nan', 'nat', 'none', 'null', '0', 'na', '#n/a', 'sin dato', 'no aplica', 'no']
    if texto.lower() in nulos: return None
    return texto

def normalizar_eps(val):
    """
    LAVADORA DE EPS: Estandariza los nombres de las aseguradoras.
    Convierte 'Asmet Salud EPS SAS' -> 'ASMET SALUD'
    """
    if pd.isna(val) or val is None or val == "": return None
    
    # 1. Limpieza básica (Mayúsculas y quitar basura)
    texto = str(val).upper().strip()
    texto = texto.replace('.', '').replace(',', '')
    
    # 2. Reglas de Mapeo (Palabra Clave -> Nombre Oficial)
    # El orden importa: busca la palabra clave dentro del texto
    reglas = {
        'ASMET': 'ASMET SALUD',
        'NUEVA': 'NUEVA EPS',
        'SANITAS': 'SANITAS',
        'SURA': 'SURA',
        'EMSSANAR': 'EMSSANAR',
        'AIC': 'AIC',
        'MALLAMAS': 'MALLAMAS',
        'SALUD TOTAL': 'SALUD TOTAL',
        'COOSALUD': 'COOSALUD',
        'FAMISANAR': 'FAMISANAR',
        'CAJACOPI': 'CAJACOPI',
        'PIJAOS': 'PIJAOS SALUD',
        'POLICIA': 'POLICIA NACIONAL',
        'FUERZAS MILITARES': 'FUERZAS MILITARES',
        'ECOOPSOS': 'ECOOPSOS',
        'MUTUAL SER': 'MUTUAL SER'
    }
    
    for clave, valor_oficial in reglas.items():
        if clave in texto:
            return valor_oficial
            
    # Si no coincide con ninguna regla, devolvemos el texto limpio quitando sufijos comunes
    texto_limpio = texto.replace(' EPS', '').replace(' SAS', '').replace(' S A S', '').strip()
    return texto_limpio

def parse_date(date_val):
    """Parsea fechas blindadas."""
    if pd.isna(date_val): return None
    if isinstance(date_val, (datetime, pd.Timestamp)): return date_val.date()
    
    s = str(date_val).strip()
    if not s or s.lower() in ['nan', 'nat', '']: return None

    s_clean = re.split(r'[ T]', s)[0]

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            return pd.to_datetime(s_clean, dayfirst=True).date()
        except:
            return None

# --- 2. LECTURA Y CARGA ---

def leer_archivo_inteligente(file_path):
    print(f"\n--- [DIAGNÓSTICO] Leyendo: {os.path.basename(file_path)} ---")
    df = None
    try:
        if file_path.endswith('.csv'):
            try: 
                df = pd.read_csv(file_path, sep=None, engine='python', header=None, dtype=str, encoding='utf-8')
                print("-> Leído como CSV (utf-8, header=None)")
            except: 
                try: df = pd.read_csv(file_path, sep=None, engine='python', header=None, dtype=str, encoding='latin-1')
                except: df = pd.read_csv(file_path, sep=';', header=None, dtype=str, encoding='latin-1')
        else:
            df = pd.read_excel(file_path, header=None, dtype=str)
            print("-> Leído como Excel (header=None)")
    except Exception as e:
        return None, f"Error archivo: {str(e)}"

    if df is None or df.empty: return None, "Archivo vacío"

    # HEADER HUNTER V4
    sample_rows = 20
    header_idx = -1
    
    keywords = [
        'identificaci', 'documento', 'apellidos', 'nombres',
        'nacimiento', 'aseguradora', 'telefono', 'direccion',
        'municipio', 'nota', 'sede'
    ]

    print(f"-> Buscando cabecera (escaneo profundo)...")

    for i in range(min(sample_rows, len(df))):
        raw_row = df.iloc[i].astype(str).tolist()
        row_norm = [normalize_header(x) for x in raw_row]
        
        matches = 0
        for cell in row_norm:
            for k in keywords:
                if k in cell:
                    matches += 1
                    break 
        
        if matches >= 2:
            header_idx = i
            print(f"✅ CABECERA DETECTADA EN FILA {i} (Coincidencias: {matches})")
            df.columns = df.iloc[i].astype(str).tolist()
            df = df.iloc[i+1:].reset_index(drop=True)
            break
            
    if header_idx == -1:
        print("⚠️ ALERTA: No se detectó cabecera clara. Usando Fila 0.")
        df.columns = df.iloc[0].astype(str).tolist()
        df = df.iloc[1:].reset_index(drop=True)

    df.columns = [normalize_header(str(c)) for c in df.columns]
    df.dropna(how='all', inplace=True)
    print(f"-> Columnas Finales: {list(df.columns)[:5]}...")
    
    return df, None

# --- 3. PROCESAMIENTO MASIVO ---

def importar_archivo_masivo(file_path):
    df, error = leer_archivo_inteligente(file_path)
    if error: return {"error": error}

    column_mapping = {
        'numero_documento': [
            'numero_de_identificacion', 'numero_de_ic', 
            'identificacion', 'cedula', 'numero_documento', 'documento', 
            'numero_de_identificaci', 'nro_identificacion'
        ],
        'tipo_documento': [
            'tipo_de_identificacion', 'tipo_identificacion',
            'tipo_de_identificaci', 'tipo_documento'
        ],
        'n1': ['nombre_1', 'primer_nombre', 'nombre_1_ic_nombre_1'], 
        'n2': ['nombre_2', 'segundo_nombre'],
        'a1': ['apellido_1', 'primer_apellido'],
        'a2': ['apellido_2', 'segundo_apellido'],
        'nombre_completo': ['nombre_completo', 'paciente', 'nombres_y_apellidos', 'nombres'],
        'genero': ['genero', 'sexo'], 'edad': ['edad'],
        'fecha_solicitud_cita': [
            'fecha_de_solicitud_de_cita', 'fecha_solicitud', 
            'fecha_de_creaci', 'fecha_de_creacion', 'fecha_creacion', 
            'numero_solicitud', 'fecha_orden'
        ],
        'fecha_cita': ['fecha_de_cita', 'fecha_cita', 'fecha_asignada'],
        'fecha_captacion': ['fecha_de_captacion', 'fecha_captacion'],
        'estado_solicitud': ['estado_de_solicitud', 'estado', 'estado_asist', 'estado_adm'], 
        'tipo_procedimiento': ['tipo_de_procedimiento', 'procedimiento', 'servicio', 'tipo_servicio'],
        'barrera': ['barrera'],
        'observaciones': ['observaciones', 'observacion'],
        'entidad_aseguradora': ['entidad_aseguradora', 'entidad_asegurdora', 'eps', 'aseguradora', 'entidad'],
        'cups': ['cups'], 'ruta': ['ruta']
    }

    rename_dict = {}
    cols_act = df.columns
    for standard, aliases in column_mapping.items():
        found = False
        for alias in aliases:
            if alias in cols_act:
                rename_dict[alias] = standard
                found = True
                break
        if not found:
            for col in cols_act:
                for alias in aliases:
                    if alias in col and standard not in rename_dict.values():
                        rename_dict[col] = standard
                        break
    
    df.rename(columns=rename_dict, inplace=True)

    if 'numero_documento' not in df.columns:
        return {"error": f"Falta columna Identificación. Se detectó: {list(df.columns[:5])}"}

    # --- PERSISTENCIA ---
    docs = set(df['numero_documento'].dropna().apply(limpiar_dato).unique())
    existing_p = Patient.objects.filter(numero_documento__in=docs).values('id', 'numero_documento')
    pmap = {p['numero_documento']: p['id'] for p in existing_p}
    
    new_ps, update_ps = [], []
    processed_p = set()

    # 1. PACIENTES
    for row in df.itertuples(index=False):
        doc = limpiar_dato(getattr(row, 'numero_documento', None))
        if not doc or doc in processed_p: continue
        
        gen = limpiar_dato(getattr(row, 'genero', None))
        try: edad = int(float(getattr(row, 'edad', 0)))
        except: edad = None
        
        n1 = limpiar_dato(getattr(row, 'n1', None))
        n2 = limpiar_dato(getattr(row, 'n2', None))
        a1 = limpiar_dato(getattr(row, 'a1', None))
        a2 = limpiar_dato(getattr(row, 'a2', None))
        full = limpiar_dato(getattr(row, 'nombre_completo', None))
        
        vn1 = n1 if n1 else (full if full else "PACIENTE")
        va1 = a1 if a1 else ""

        if doc in pmap:
            p = Patient(id=pmap[doc])
            if vn1 != "PACIENTE": p.nombre_1 = vn1.upper()[:99]
            if n2: p.nombre_2 = n2.upper()[:99]
            if va1: p.apellido_1 = va1.upper()[:99]
            if a2: p.apellido_2 = a2.upper()[:99]
            if gen: p.genero = gen
            if edad: p.edad = edad
            update_ps.append(p)
        else:
            new_ps.append(Patient(
                numero_documento=doc, tipo_documento='CC',
                nombre_1=vn1.upper()[:99], nombre_2=n2.upper()[:99] if n2 else None,
                apellido_1=va1.upper()[:99], apellido_2=a2.upper()[:99] if a2 else None,
                genero=gen, edad=edad
            ))
        processed_p.add(doc)

    if new_ps:
        Patient.objects.bulk_create(new_ps, batch_size=500, ignore_conflicts=True)
        new_db = Patient.objects.filter(numero_documento__in=docs).values('id', 'numero_documento')
        for p in new_db: pmap[p['numero_documento']] = p['id']
    
    if update_ps:
        Patient.objects.bulk_update(update_ps, ['nombre_1','nombre_2','apellido_1','apellido_2','genero','edad'], batch_size=500)

    # 2. SEGUIMIENTOS
    new_fs = []
    existing_sigs = set()
    if pmap:
        db_sigs = FollowUp.objects.filter(patient_id__in=pmap.values()).values_list('patient_id', 'fecha_solicitud_cita', 'tipo_procedimiento')
        for s in db_sigs:
            d_str = str(s[1]) if s[1] else "None"
            existing_sigs.add((s[0], d_str, normalize_text(s[2] or "")))

    print("-> Procesando Seguimientos...")
    
    for row in df.itertuples(index=False):
        doc = limpiar_dato(getattr(row, 'numero_documento', None))
        pid = pmap.get(doc)
        if not pid: continue

        d_sol = parse_date(getattr(row, 'fecha_solicitud_cita', None))
        if not d_sol: d_sol = parse_date(getattr(row, 'fecha_captacion', None))
        d_sol_str = str(d_sol) if d_sol else "None"
        
        proc_clean = normalize_text(limpiar_dato(getattr(row, 'tipo_procedimiento', None)) or "CONSULTA")
        
        sig = (pid, d_sol_str, proc_clean)
        if sig in existing_sigs: continue

        est_raw = normalize_text(getattr(row, 'estado_solicitud', 'PENDIENTE'))
        estado = 'PENDIENTE'
        if 'realiz' in est_raw or 'efectiv' in est_raw: estado = 'REALIZADO'
        elif 'agen' in est_raw: estado = 'AGENDADO'
        elif 'cancel' in est_raw: estado = 'CANCELADO'
        elif 'gest' in est_raw: estado = 'EN_GESTION'

        # AQUÍ USAMOS LA NORMALIZACIÓN DE EPS
        eps_raw = getattr(row, 'entidad_aseguradora', None)
        eps_clean = normalizar_eps(eps_raw) # <--- ¡EL CAMBIO MÁGICO!

        new_fs.append(FollowUp(
            patient_id=pid,
            tipo_procedimiento=proc_clean.upper(),
            fecha_solicitud_cita=d_sol,
            estado_solicitud=estado,
            fecha_cita=parse_date(getattr(row, 'fecha_cita', None)),
            barrera=limpiar_dato(getattr(row, 'barrera', None)),
            observaciones=limpiar_dato(getattr(row, 'observaciones', None)),
            entidad_aseguradora=eps_clean, # Usamos el limpio
            cups=limpiar_dato(getattr(row, 'cups', None)),
            ruta=limpiar_dato(getattr(row, 'ruta', None))
        ))
        existing_sigs.add(sig)

    if new_fs:
        FollowUp.objects.bulk_create(new_fs, batch_size=500)

    return {"success": True, "registros": len(new_fs), "actualizados": len(update_ps)}

# --- 4. MÉTRICAS (Simplificadas con lógica DB) ---

def compute_request_status_from_db(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    active = queryset.exclude(estado_solicitud__icontains='CANCELADO')
    total = active.count()
    if total == 0: return {"labels": [], "values": [], "completados": 0, "pendientes": 0, "porcentaje_completado": 0}
    realizados = active.filter(estado_solicitud__icontains='REALIZADO').count()
    agendados = active.filter(estado_solicitud__icontains='AGENDADO').count()
    pendientes = active.filter(Q(estado_solicitud__icontains='PENDIENTE') | Q(estado_solicitud__icontains='GESTION')).count()
    return {"labels": ["Realizado", "Agendado", "Pendiente"], "values": [realizados, agendados, pendientes], "completados": realizados, "pendientes": pendientes+agendados, "porcentaje_completado": round((realizados/total)*100, 1)}

def compute_barriers(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    data = queryset.exclude(Q(barrera__isnull=True)|Q(barrera__exact='')).values('barrera').annotate(total=Count('id')).order_by('-total')[:5]
    return {"labels": [x['barrera'] for x in data], "values": [x['total'] for x in data]}

def compute_opportunity_by_procedure(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    data = queryset.values('tipo_procedimiento').annotate(total=Count('id')).order_by('-total')[:10]
    return {"procedimiento_labels": json.dumps([str(x['tipo_procedimiento'])[:20] for x in data]), "values": [x['total'] for x in data]}

def compute_institutional_metrics_db():
    gender_qs = Patient.objects.values('genero').annotate(total=Count('id')).order_by('-total')
    g_labels = [x['genero'] or 'SIN DATO' for x in gender_qs]
    g_values = [x['total'] for x in gender_qs]
    
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
    
    # EPS (Normalizadas)
    eps_qs = FollowUp.objects.exclude(Q(entidad_aseguradora__isnull=True)|Q(entidad_aseguradora__exact='')).values('entidad_aseguradora').annotate(total=Count('id')).order_by('-total')[:10]
    e_labels = [str(x['entidad_aseguradora'])[:30] for x in eps_qs]
    e_values = [x['total'] for x in eps_qs]
    
    barrier_qs = FollowUp.objects.exclude(Q(barrera__isnull=True)|Q(barrera__exact='')).values('barrera').annotate(total=Count('id')).order_by('-total')[:10]
    b_labels = [str(x['barrera'])[:40] for x in barrier_qs]
    b_values = [x['total'] for x in barrier_qs]
    
    month_qs = FollowUp.objects.annotate(month=TruncMonth('fecha_solicitud_cita')).values('month').annotate(total=Count('id')).order_by('month')
    m_labels = [x['month'].strftime('%b %Y') for x in month_qs if x['month']]
    m_values = [x['total'] for x in month_qs if x['month']]

    return {
        'gender_labels': json.dumps(g_labels), 'gender_values': json.dumps(g_values),
        'age_labels': json.dumps(list(rangos.keys())), 'age_values': json.dumps(list(rangos.values())),
        'eps_labels': json.dumps(e_labels), 'eps_values': json.dumps(e_values),
        'barrier_labels': json.dumps(b_labels), 'barrier_values': json.dumps(b_values),
        'month_labels': json.dumps(m_labels), 'cnt_values': json.dumps(m_values),
    }