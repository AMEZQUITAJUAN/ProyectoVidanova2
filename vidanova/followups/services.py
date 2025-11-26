import os
import unicodedata
import pandas as pd
import numpy as np
import json
import csv
from datetime import date
from django.db import transaction
from django.conf import settings
from django.db.models import Count, Q
from patients.models import Patient
from .models import FollowUp

# --- UTILIDADES BÁSICAS ---

def normalize_columns(cols):
    """
    Normaliza nombres de columnas eliminando tildes, espacios y caracteres raros.
    """
    def clean(c):
        if not isinstance(c, str): return str(c)
        c = c.strip().lower()
        # Eliminar BOM (Byte Order Mark) que a veces traen los CSV de Excel
        c = c.replace('\ufeff', '')
        c = unicodedata.normalize('NFKD', c).encode('ascii', 'ignore').decode('utf-8')
        c = c.replace(" ", "_").replace("__", "_").replace(".", "").replace("\n", "")
        return c
    return [clean(x) for x in cols]

def save_processed_dataframe(df, filename="processed_latest.csv"):
    uploads_dir = os.path.join(settings.MEDIA_ROOT, "uploads")
    os.makedirs(uploads_dir, exist_ok=True)
    processed_path = os.path.join(uploads_dir, filename)
    df.to_csv(processed_path, index=False, encoding='utf-8-sig')
    return processed_path

def limpiar_dato(val):
    """Limpia cadenas, elimina '.0', maneja nulos y espacios."""
    if pd.isna(val) or val is None:
        return ''
    texto = str(val).strip()
    if texto.endswith('.0'):
        texto = texto[:-2]
    if texto.lower() in ['nan', 'nat', 'none', 'null', '0', 'na', '#n/a', 'sin dato', 'undefined']:
        return ''
    return texto

def parse_date(date_val):
    """Convierte fechas robustas (Excel serial, Strings dd/mm/yyyy, etc)."""
    if pd.isna(date_val): return None
    s = str(date_val).strip().lower()
    if not s or s in ['nan', 'nat', 'none', '']: return None

    try:
        # dayfirst=True es clave para LATAM (dd/mm/yyyy)
        dt = pd.to_datetime(date_val, dayfirst=True, errors='coerce')
        if pd.isna(dt): return None
        return dt.date()
    except:
        return None

# --- LECTURA INTELIGENTE DE ARCHIVOS ---

def leer_archivo_inteligente(file_path):
    """
    Intenta leer CSV o Excel probando diferentes codificaciones y separadores.
    Busca la fila de encabezado correcta si no está en la fila 0.
    """
    df = None
    errores = []

    # 1. Intentar leer según extensión
    try:
        if file_path.endswith('.xlsx') or file_path.endswith('.xls'):
            df = pd.read_excel(file_path, dtype=str)
        elif file_path.endswith('.csv'):
            # Intento 1: Detección automática de motor Python (más lento pero inteligente)
            try:
                df = pd.read_csv(file_path, sep=None, engine='python', dtype=str, encoding='utf-8')
            except UnicodeDecodeError:
                # Intento 2: Encoding Latin-1 (típico Windows Excel) y separador ;
                df = pd.read_csv(file_path, sep=';', dtype=str, encoding='latin-1')
            except Exception:
                # Intento 3: Separador coma estándar
                df = pd.read_csv(file_path, sep=',', dtype=str, encoding='latin-1')
    except Exception as e:
        return None, f"Error crítico leyendo archivo: {str(e)}"

    if df is None:
        return None, "No se pudo leer el archivo con ningún formato conocido."

    # 2. BUSCADOR DE CABECERAS (HEADER HUNTER)
    # A veces el reporte empieza en la fila 3 o 4. Buscamos columnas clave.
    
    # Lista de columnas que DEBEN existir (versión normalizada)
    columnas_clave = ['identificacion', 'cedula', 'numero_documento', 'documento', 'id']
    
    # Normalizamos las columnas actuales
    cols_actuales = normalize_columns(df.columns)
    
    # Si encontramos una clave en la fila 0, retornamos
    if any(k in cols_actuales for k in columnas_clave):
        df.columns = cols_actuales
        return df, None

    # Si no, escaneamos las primeras 10 filas buscando la cabecera
    for i in range(1, min(15, len(df))):
        posible_header = df.iloc[i].astype(str).tolist()
        posible_header_norm = normalize_columns(posible_header)
        
        if any(k in posible_header_norm for k in columnas_clave):
            # Encontramos la cabecera real en la fila i
            # Reiniciamos el DF usando esa fila como header
            df.columns = posible_header_norm # Asignamos nombres
            df = df.iloc[i+1:].reset_index(drop=True) # Cortamos datos
            return df, None

    return None, f"No se encontró la columna 'Identificación' o 'Cédula' en las primeras filas. Columnas leídas: {list(df.columns[:5])}..."

# --- LÓGICA PRINCIPAL ---

def importar_archivo_masivo(file_path):
    # 1. Leer Archivo (CSV o Excel) de forma robusta
    df, error = leer_archivo_inteligente(file_path)
    if error:
        return {"error": error}

    # 2. MAPEO DE COLUMNAS 
    # (Tus columnas confirmadas + variaciones comunes)
    column_mapping = {
        'numero_documento': ['identificacion', 'numero_de_identificacion', 'cedula', 'numero_documento', 'id', 'documento', 'nro_identificacion'],
        'tipo_documento': ['tipo_de_identificacion', 'tipo_identificacion', 'tipo_doc', 'td'],
        'n1': ['nombre_1', 'primer_nombre'],
        'n2': ['nombre_2', 'segundo_nombre'],
        'a1': ['apellido_1', 'primer_apellido'],
        'a2': ['apellido_2', 'segundo_apellido'],
        'nombre_completo': ['paciente', 'nombre_completo', 'nombres_y_apellidos', 'nombre', 'usuario'],
        'fecha_solicitud_cita': ['fecha_de_solicitud', 'fecha_solicitud', 'f_solicitud', 'fecha_orden', 'fecha_de_solicitud_de_cita', 'fecha_radicacion'],
        'fecha_cita': ['fecha_de_cita', 'fecha_cita', 'f_cita', 'fecha_asignada'],
        'fecha_captacion': ['fecha_de_captacion', 'fecha_captacion'],
        'fecha_atencion': ['fecha_de_atencion', 'fecha_atencion'],
        'tipo_procedimiento': ['tipo_de_procedimiento', 'procedimiento', 'servicio', 'tipo_servicio', 'estudio', 'examen'],
        'estado_solicitud': ['estado_de_solicitud', 'estado', 'estado_actual', 'status', 'estado_cita'],
        'barrera': ['barrera', 'motivo_de_barrera', 'causa_inejecucion'],
        'observaciones': ['observaciones', 'obs', 'notas', 'comentarios'],
        'entidad_aseguradora': ['entidad_aseguradora', 'entidad_asegurdora', 'eps', 'aseguradora', 'pagador'],
        'cups': ['cups', 'codigo_cups'],
        'ruta': ['ruta']
    }

    # Normalizar headers del DF actual
    df.columns = normalize_columns(df.columns)
    
    # Renombrar
    rename_dict = {}
    for real_col, aliases in column_mapping.items():
        for alias in aliases:
            norm_aliases = normalize_columns([alias])
            for norm in norm_aliases:
                if norm in df.columns:
                    rename_dict[norm] = real_col
                    break 
    
    df.rename(columns=rename_dict, inplace=True)
    df = df.loc[:, ~df.columns.duplicated()] # Eliminar columnas duplicadas

    if 'numero_documento' not in df.columns:
        return {"error": f"Falta columna de Identificación. Se detectaron: {list(df.columns)}"}

    # 3. GESTIÓN DE PACIENTES
    existing_patients = dict(Patient.objects.values_list('numero_documento', 'id'))
    patients_to_create = []
    seen_docs = set()

    for index, row in df.iterrows():
        doc = limpiar_dato(row.get('numero_documento'))
        if not doc or doc in existing_patients or doc in seen_docs:
            continue

        n1 = limpiar_dato(row.get('n1'))
        n2 = limpiar_dato(row.get('n2'))
        a1 = limpiar_dato(row.get('a1'))
        a2 = limpiar_dato(row.get('a2'))
        full_name = " ".join([p for p in [n1, n2, a1, a2] if p])
        
        if not full_name:
            full_name = limpiar_dato(row.get('nombre_completo')) or 'PACIENTE SIN NOMBRE'

        patients_to_create.append(Patient(
            numero_documento=doc,
            nombre_1=full_name.upper(),
            tipo_documento=limpiar_dato(row.get('tipo_documento')) or 'CC'
        ))
        seen_docs.add(doc)

    if patients_to_create:
        Patient.objects.bulk_create(patients_to_create, ignore_conflicts=True)
        existing_patients = dict(Patient.objects.values_list('numero_documento', 'id'))

    # 4. GESTIÓN DE SEGUIMIENTOS (UPSERT)
    all_f = FollowUp.objects.values('id', 'patient_id', 'fecha_solicitud_cita', 'tipo_procedimiento')
    existing_map = {} 
    
    # Mapa optimizado para detectar si ya existe
    for item in all_f:
        d = item['fecha_solicitud_cita']
        # Usamos string para proc y fecha para evitar problemas de tipos
        proc_key = str(item['tipo_procedimiento']).upper().strip()
        existing_map[(item['patient_id'], d, proc_key)] = item['id']

    to_create = []
    batch_update_instances = []

    for index, row in df.iterrows():
        doc = limpiar_dato(row.get('numero_documento'))
        pid = existing_patients.get(doc)
        if not pid: continue

        # Normalización clave
        proc = limpiar_dato(row.get('tipo_procedimiento')) or 'CONSULTA'
        proc = proc.upper()
        
        d_sol = parse_date(row.get('fecha_solicitud_cita'))
        
        # Si no hay fecha de solicitud, usamos la fecha de atención o captación como fallback para la firma
        if not d_sol:
             d_sol = parse_date(row.get('fecha_captacion'))

        d_cita = parse_date(row.get('fecha_cita'))
        
        estado_raw = str(row.get('estado_solicitud', 'PENDIENTE')).upper()
        estado = 'PENDIENTE'
        if 'REALIZ' in estado_raw: estado = 'REALIZADO'
        elif 'AGEN' in estado_raw: estado = 'AGENDADO'
        elif 'CANCEL' in estado_raw: estado = 'CANCELADO'
        elif 'GEST' in estado_raw: estado = 'EN_GESTION'

        signature = (pid, d_sol, proc)

        if signature in existing_map:
            # ACTUALIZAR
            f_id = existing_map[signature]
            f_obj = FollowUp(id=f_id)
            f_obj.estado_solicitud = estado
            f_obj.fecha_cita = d_cita
            f_obj.barrera = limpiar_dato(row.get('barrera'))
            f_obj.observaciones = limpiar_dato(row.get('observaciones'))
            f_obj.entidad_aseguradora = limpiar_dato(row.get('entidad_aseguradora'))
            batch_update_instances.append(f_obj)
        else:
            # CREAR
            new_f = FollowUp(
                patient_id=pid,
                tipo_procedimiento=proc,
                fecha_solicitud_cita=d_sol,
                estado_solicitud=estado,
                fecha_cita=d_cita,
                fecha_captacion=parse_date(row.get('fecha_captacion')),
                fecha_atencion=parse_date(row.get('fecha_atencion')),
                barrera=limpiar_dato(row.get('barrera')),
                observaciones=limpiar_dato(row.get('observaciones')),
                entidad_aseguradora=limpiar_dato(row.get('entidad_aseguradora')),
                cups=limpiar_dato(row.get('cups')),
                ruta=limpiar_dato(row.get('ruta'))
            )
            to_create.append(new_f)
            # Evitar duplicados dentro del mismo archivo
            existing_map[signature] = 0 

    # 5. COMMIT
    with transaction.atomic():
        if to_create:
            FollowUp.objects.bulk_create(to_create, batch_size=1000)
        if batch_update_instances:
            # Solo actualizamos campos que cambian frecuentemente
            fields = ['estado_solicitud', 'fecha_cita', 'barrera', 'observaciones', 'entidad_aseguradora']
            FollowUp.objects.bulk_update(batch_update_instances, fields=fields, batch_size=1000)
    
    try:
        save_processed_dataframe(df)
    except:
        pass # No fallar si no se puede guardar el backup

    return {
        "success": True,
        "mensaje": "Carga completada",
        "registros": len(to_create),
        "actualizados": len(batch_update_instances)
    }

# --- METRICAS DB (Sin cambios) ---
def compute_request_status_from_db(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    active = queryset.exclude(estado_solicitud='CANCELADO')
    total = active.count()
    if total == 0: return {"labels": ["Sin Datos"], "values": [0], "completados": 0, "pendientes": 0, "porcentaje_completado": 0}
    
    realizados = active.filter(estado_solicitud='REALIZADO').count()
    agendados = active.filter(estado_solicitud='AGENDADO').count()
    pendientes = active.filter(estado_solicitud__in=['PENDIENTE', 'EN_GESTION', 'POR_GESTIONAR']).count()
    
    return {
        "labels": ["Realizado", "Agendado", "Pendiente"],
        "values": [realizados, agendados, pendientes],
        "completados": realizados,
        "pendientes": pendientes + agendados,
        "porcentaje_completado": round((realizados/total)*100, 1)
    }

def compute_barriers(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    data = queryset.exclude(Q(barrera__isnull=True)|Q(barrera='')).values('barrera').annotate(total=Count('id')).order_by('-total')[:5]
    return {"labels": [x['barrera'] for x in data], "values": [x['total'] for x in data]}

def compute_opportunity_by_procedure(queryset=None):
    if queryset is None: queryset = FollowUp.objects.all()
    
    # Obtenemos los datos
    data = queryset.values('tipo_procedimiento').annotate(total=Count('id')).order_by('-total')[:10]
    
    # TRUCO VISUAL: Recortar nombres largos para que la gráfica no explote
    labels = []
    for x in data:
        proc = str(x['tipo_procedimiento'])
        # Si mide más de 20 letras, lo cortamos y ponemos "..."
        if len(proc) > 20:
            labels.append(proc[:20] + "...")
        else:
            labels.append(proc)
            
    return {
        "procedimiento_labels": json.dumps(labels), # Usamos los recortados
        "values": [x['total'] for x in data]
    }
def compute_institutional_metrics_db():
    return {'gender_labels': '[]', 'gender_values': '[]'}