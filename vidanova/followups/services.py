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
from .models import FollowUp, MasterCUP

# --- 1. UTILIDADES ---

def normalize_text(text):
    if not isinstance(text, str): return str(text) if text is not None else ""
    text = text.strip().lower()
    text = text.replace('\ufeff', '')
    text = unicodedata.normalize('NFKD', text).encode('ascii', 'ignore').decode('utf-8')
    return text

def normalize_header(text):
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

# --- TRADUCTORA DE ESTADOS (NUEVO) ---
def normalizar_estado_detallado(texto_raw):
    """
    Traduce los 15 estados detallados del Excel a los 5 estados del Sistema.
    """
    if not texto_raw: return 'PENDIENTE'
    t = str(texto_raw).upper().strip()
    
    # 1. REALIZADO (Verde)
    if 'CUMPLIDO' in t or 'REALIZADO' in t: return 'REALIZADO'
    
    # 2. AGENDADO (Azul)
    if 'AGENDADO' in t: return 'AGENDADO'
    
    # 3. CANCELADO (Gris/Rojo Oscuro)
    if 'FALLECIDO' in t or 'NO ACEPTA' in t or 'CANCELADO' in t: return 'CANCELADO'
    
    # 4. EN GESTIÓN (Amarillo/Naranja) - Aquí entra la mayoría de tu tabla
    gestiones = ['PROGRAMACION', 'PROGRAMACIÓN', 'AVAL', 'AUTORIZACION', 'HOSPITALIZADO', 'PENDIENTE RESULTADO', 'CAMBIO DE ORDENES']
    if any(g in t for g in gestiones): return 'EN_GESTION'
    
    # 5. PENDIENTE (Naranja) - Casos diferidos o controles lejanos
    if 'DIFERIDO' in t or 'CONTROL' in t: return 'PENDIENTE'
    
    # Default
    return 'PENDIENTE'

def normalizar_eps(val):
    if pd.isna(val) or val is None or val == "": return None
    texto = str(val).upper().strip()
    texto = texto.replace('.', '').replace(',', '')
    reglas = {
        'ASMET': 'ASMET SALUD', 'NUEVA': 'NUEVA EPS', 'SANITAS': 'SANITAS',
        'SURA': 'SURA', 'EMSSANAR': 'EMSSANAR', 'AIC': 'AIC',
        'MALLAMAS': 'MALLAMAS', 'SALUD TOTAL': 'SALUD TOTAL',
        'COOSALUD': 'COOSALUD', 'FAMISANAR': 'FAMISANAR',
        'CAJACOPI': 'CAJACOPI', 'PIJAOS': 'PIJAOS SALUD',
        'POLICIA': 'POLICIA NACIONAL', 'ECOOPSOS': 'ECOOPSOS',
        'MUTUAL SER': 'MUTUAL SER'
    }
    for clave, valor_oficial in reglas.items():
        if clave in texto: return valor_oficial
    return texto.replace(' EPS', '').replace(' SAS', '').strip()

def obtener_agrupador(codigo_cie10):
    """Calcula el Agrupador (25 Grupos CAC) basado en el código CIE10."""
    if not codigo_cie10: return None
    c = str(codigo_cie10).upper().replace('.', '').strip()
    
    # 1-7. PRINCIPALES
    if c.startswith('C50'): return "1= CAC Mama"
    if c.startswith('C61'): return "2= CAC Próstata"
    if c.startswith('C53') or c.startswith('D06'): return "3= CAC Cérvix"
    if c.startswith('C18') or c.startswith('C19') or c.startswith('C20') or c.startswith('C21'): return "4= CAC Colorectal"
    if c.startswith('C16'): return "5= CAC Estómago"
    if c.startswith('C43') or c.startswith('D03'): return "6= CAC Melanoma"
    if c.startswith('C33') or c.startswith('C34'): return "7= CAC Pulmón"
    
    # 8-11. HEMATO
    if c.startswith('C81'): return "8= CAC Linfoma Hodgkin"
    if c.startswith('C82') or c.startswith('C83') or c.startswith('C84') or c.startswith('C85') or c.startswith('C96'): return "9= CAC Linfoma No Hodgkin"
    if c == 'C910': return "10= CAC Leucemia Linfocítica Aguda"
    if c.startswith('C92'): return "11= CAC Leucemia Mielocítica Aguda"
    
    # 12-16. OTROS SITIOS COMUNES
    if c.startswith('C0') or c.startswith('C10') or c.startswith('C11') or c.startswith('C12') or c.startswith('C13') or c.startswith('C14'): return "12= Labio, cavidad bucal y faringe"
    if c.startswith('C15') or c.startswith('C17') or c.startswith('C22') or c.startswith('C23') or c.startswith('C24') or c.startswith('C25') or c.startswith('C26'): return "13= Otros órganos digestivos"
    if c.startswith('C30') or c.startswith('C31') or c.startswith('C32') or c.startswith('C37') or c.startswith('C38') or c.startswith('C39'): return "14= Otros órganos respiratorios e intratorácicos"
    if c.startswith('C40') or c.startswith('C41'): return "15= Huesos y cartílagos articulares"
    if c.startswith('C44') or c.startswith('D04'): return "16= Otros tumores de la piel"

    # 17-25. RESTO DE GRUPOS (NUEVOS)
    if c.startswith('C45') or c.startswith('C46') or c.startswith('C47') or c.startswith('C48') or c.startswith('C49'): return "17= Tejidos mesoteliales y blandos"
    if c.startswith('C51') or c.startswith('C52') or c.startswith('C54') or c.startswith('C55') or c.startswith('C56') or c.startswith('C57') or c.startswith('C58'): return "18= Otros órganos genitales femeninos"
    if c.startswith('C60') or c.startswith('C62') or c.startswith('C63'): return "19= Otros órganos genitales masculinos"
    if c.startswith('C64') or c.startswith('C65') or c.startswith('C66') or c.startswith('C67') or c.startswith('C68'): return "20= Vías urinarias (Riñón/Vejiga)"
    if c.startswith('C69') or c.startswith('C70') or c.startswith('C71') or c.startswith('C72'): return "21= Ojo, encéfalo y sistema nervioso central"
    if c.startswith('C73') or c.startswith('C74') or c.startswith('C75'): return "22= Glándulas tiroides y endocrinas"
    if c.startswith('C76') or c.startswith('C80'): return "23= Sitios mal definidos / No especificados"
    if c.startswith('C88') or c.startswith('C90') or c.startswith('C91') or c.startswith('C93') or c.startswith('C94') or c.startswith('C95'): 
        if c != 'C910': return "24= Otros tumores tejido linfático/hematopoyético"
    if c.startswith('C77') or c.startswith('C78') or c.startswith('C79'): return "25= Tumores secundarios"

    return "Otros Diagnósticos"

def calcular_procedimiento(cups_raw, texto_raw, desc_extra=None):
    """
    Sistema Híbrido + Auto-Mejora:
    1. Busca en Tabla Maestra.
    2. Si existe, revisa si el texto nuevo es mejor que el guardado y lo actualiza.
    """
    grupo_final = "PENDIENTE CLASIFICAR"
    codigo_limpio = None

    # Definimos cuál es la mejor descripción disponible
    # Preferimos desc_extra (Columna Servicio) sobre texto_raw (Columna Tipo/Grupo)
    mejor_descripcion = str(desc_extra).strip() if desc_extra else (str(texto_raw).strip() if texto_raw else "")

    # A. INTENTO POR MAESTRO DE CUPS
    if cups_raw:
        codigo_limpio = str(cups_raw).strip().upper()
        
        try:
            maestro = MasterCUP.objects.get(codigo=codigo_limpio)
            
            # --- AUTO-MEJORA ---
            desc_actual = maestro.descripcion or ""
            # Si la nueva descripción es más larga/detallada, actualizamos el maestro
            if mejor_descripcion and (len(mejor_descripcion) > len(desc_actual) or desc_actual == "Importado Automáticamente"):
                maestro.descripcion = mejor_descripcion[:250]
                maestro.save()
            # -------------------

            if maestro.grupo != 'PENDIENTE':
                return maestro.grupo
                
        except MasterCUP.DoesNotExist:
            pass

    # B. HEURÍSTICA
    sugerencia = "PENDIENTE"
    # Usamos el texto para adivinar la categoría
    texto_analisis = mejor_descripcion.upper()
    
    if codigo_limpio:
        if codigo_limpio.startswith('89'): sugerencia = "CONSULTA"
        elif codigo_limpio.startswith('90') or codigo_limpio.startswith('91'): sugerencia = "LABORATORIO"
        elif codigo_limpio.startswith('87') or codigo_limpio.startswith('88'): sugerencia = "IMAGEN"
        elif codigo_limpio.startswith('9925'): sugerencia = "QUIMIOTERAPIA"
        elif codigo_limpio.startswith('92'): sugerencia = "RADIOTERAPIA"
        elif codigo_limpio.startswith('6') or codigo_limpio.startswith('7') or codigo_limpio.startswith('86'): sugerencia = "CIRUGIA"
    
    if sugerencia == "PENDIENTE" and texto_analisis:
        if 'CONSULTA' in texto_analisis: sugerencia = "CONSULTA"
        elif 'QUIMIO' in texto_analisis: sugerencia = "QUIMIOTERAPIA"
        elif 'RADIO' in texto_analisis: sugerencia = "RADIOTERAPIA"
        elif 'IMAGEN' in texto_analisis or 'TAC' in texto_analisis or 'ECOGRAFIA' in texto_analisis: sugerencia = "IMAGEN"
        elif 'LAB' in texto_analisis: sugerencia = "LABORATORIO"
        elif 'CIRUGIA' in texto_analisis: sugerencia = "CIRUGIA"

    # C. APRENDIZAJE
    if codigo_limpio:
        MasterCUP.objects.get_or_create(
            codigo=codigo_limpio,
            defaults={
                'grupo': sugerencia,
                'descripcion': mejor_descripcion[:250] if mejor_descripcion else "Importado Automáticamente"
            }
        )

    # Retornamos la categoría calculada
    return sugerencia if sugerencia != "PENDIENTE" else (texto_raw or "SIN CLASIFICAR")

def parse_date(date_val):
    if pd.isna(date_val): return None
    if isinstance(date_val, (datetime, pd.Timestamp)): return date_val.date()
    s = str(date_val).strip()
    if not s or s.lower() in ['nan', 'nat', '']: return None
    s_clean = re.split(r'[ T]', s)[0]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try: return pd.to_datetime(s_clean, dayfirst=True).date()
        except: 
            try: return pd.to_datetime(s_clean).date()
            except: return None

# --- 2. LECTURA ---
def leer_archivo_inteligente(file_path):
    print(f"\n--- [DIAGNÓSTICO] Leyendo: {os.path.basename(file_path)} ---")
    df = None
    try:
        if file_path.endswith('.csv'):
            try: df = pd.read_csv(file_path, sep=None, engine='python', header=None, dtype=str, encoding='utf-8')
            except: 
                try: df = pd.read_csv(file_path, sep=None, engine='python', header=None, dtype=str, encoding='latin-1')
                except: df = pd.read_csv(file_path, sep=';', header=None, dtype=str, encoding='latin-1')
        else:
            df = pd.read_excel(file_path, header=None, dtype=str)
    except Exception as e: return None, f"Error archivo: {str(e)}"

    if df is None or df.empty: return None, "Archivo vacío"

    sample_rows = 20
    header_idx = -1
    keywords = ['identificaci', 'documento', 'apellidos', 'nombres', 'nacimiento', 'aseguradora', 'telefono', 'nota', 'sede']

    print(f"-> Buscando cabecera...")
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
            print(f"✅ CABECERA EN FILA {i}")
            df.columns = df.iloc[i].astype(str).tolist()
            df = df.iloc[i+1:].reset_index(drop=True)
            break
            
    if header_idx == -1:
        print("⚠️ ALERTA: Usando Fila 0.")
        df.columns = df.iloc[0].astype(str).tolist()
        df = df.iloc[1:].reset_index(drop=True)

    df.columns = [normalize_header(str(c)) for c in df.columns]
    df.dropna(how='all', inplace=True)
    return df, None

# --- 3. PROCESAMIENTO ---

def importar_archivo_masivo(file_path):
    df, error = leer_archivo_inteligente(file_path)
    if error: return {"error": error}

    column_mapping = {
        # IDENTIFICACIÓN
        'numero_documento': [
            'numero_de_identificacion', 'numero_de_ic', 
            'identificacion', 'cedula', 'numero_documento', 'documento', 
            'numero_de_identificaci', 'nro_identificacion'
        ],
        'tipo_documento': [
            'tipo_de_identificacion', 'tipo_identificacion', 
            'tipo_de_identificaci', 'tipo_documento'
        ],
        
        # NOMBRES
        'n1': ['nombre_1', 'primer_nombre', 'nombre_1_ic_nombre_1'], 
        'n2': ['nombre_2', 'segundo_nombre'],
        'a1': ['apellido_1', 'primer_apellido'],
        'a2': ['apellido_2', 'segundo_apellido'],
        'nombre_completo': ['nombre_completo', 'paciente', 'nombres_y_apellidos', 'nombres'],
        
        # DEMOGRÁFICOS
        'genero': ['genero', 'sexo'], 
        'edad': ['edad'],
        'telefono': ['telefono', 'telefonos', 'celular', 'movil', 'contacto'], # <--- TU CAMBIO
        
        # FECHAS
        'fecha_solicitud_cita': [
            'fecha_de_solicitud_de_cita', 'fecha_solicitud', 
            'fecha_de_creaci', 'fecha_creacion', 'numero_solicitud', 'fecha_orden'
        ],
        'fecha_cita': ['fecha_de_cita', 'fecha_cita', 'fecha_asignada'],
        'fecha_captacion': ['fecha_de_captacion', 'fecha_captacion'],
        
        # GESTIÓN Y CLASIFICACIÓN
        'estado_solicitud': ['estado_de_la_solicitud', 'estado_de_solicitud', 'estado', 'estado_asist', 'estado_adm'], 
        
        # OJO: Sacamos 'servicio' de aquí para leerlo aparte y mejorar los nombres
        'tipo_procedimiento': ['tipo_de_procedimiento', 'procedimiento', 'tipo_servicio', 'grupo'],
        'descripcion_servicio': ['servicio', 'nombre_servicio', 'descripcion', 'nombre_procedimiento'], # <--- NUEVO PARA EL MAESTRO
        
        'barrera': ['barrera'],
        'observaciones': ['observaciones', 'observacion'],
        'entidad_aseguradora': ['entidad_aseguradora', 'entidad_asegurdora', 'eps', 'aseguradora', 'entidad'],
        'cups': ['cups'], 
        'ruta': ['ruta'],
        'codigo_diagnostico': ['codigo_diagnostico', 'codigo_cie10', 'cie10', 'cod_dx', 'dx_principal'],
        
        # NUEVOS CAMPOS DE TU TABLA
        'prestador': ['prestador'], 
        'tipo_paciente': ['tipo_de_caso', 'tipo_caso', 'tipo_de_paciente'] 
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
            # Búsqueda parcial (backup)
            for col in cols_act:
                for alias in aliases:
                    if alias in col and standard not in rename_dict.values():
                        rename_dict[col] = standard
                        break
    
    df.rename(columns=rename_dict, inplace=True)

    if 'numero_documento' not in df.columns:
        return {"error": f"Falta columna Identificación. Se detectó: {list(df.columns[:5])}"}

    # --- 1. GESTIÓN DE PACIENTES ---
    docs = set(df['numero_documento'].dropna().apply(limpiar_dato).unique())
    existing_p = Patient.objects.filter(numero_documento__in=docs).values('id', 'numero_documento')
    pmap = {p['numero_documento']: p['id'] for p in existing_p}
    
    new_ps, update_ps = [], []
    processed_p = set()

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
        
        # Captura de teléfono
        tel = limpiar_dato(getattr(row, 'telefono', None))

        if doc in pmap:
            p = Patient(id=pmap[doc])
            if vn1 != "PACIENTE": p.nombre_1 = vn1.upper()[:99]
            if n2: p.nombre_2 = n2.upper()[:99]
            if va1: p.apellido_1 = va1.upper()[:99]
            if a2: p.apellido_2 = a2.upper()[:99]
            if gen: p.genero = gen
            if edad: p.edad = edad
            if tel: p.telefono = tel
            update_ps.append(p)
        else:
            new_ps.append(Patient(
                numero_documento=doc, tipo_documento='CC',
                nombre_1=vn1.upper()[:99], nombre_2=n2.upper()[:99] if n2 else None,
                apellido_1=va1.upper()[:99], apellido_2=a2.upper()[:99] if a2 else None,
                genero=gen, edad=edad, telefono=tel
            ))
        processed_p.add(doc)

    if new_ps:
        Patient.objects.bulk_create(new_ps, batch_size=500, ignore_conflicts=True)
        new_db = Patient.objects.filter(numero_documento__in=docs).values('id', 'numero_documento')
        for p in new_db: pmap[p['numero_documento']] = p['id']
    
    if update_ps:
        Patient.objects.bulk_update(update_ps, ['nombre_1','nombre_2','apellido_1','apellido_2','genero','edad', 'telefono'], batch_size=500)

    # --- 2. GESTIÓN DE SEGUIMIENTOS ---
    new_fs = []
    existing_sigs = set()
    if pmap:
        # Cache de firmas para evitar duplicados en BD
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
        
        # DATOS PARA CLASIFICACIÓN INTELIGENTE
        cups_raw = limpiar_dato(getattr(row, 'cups', None))
        texto_grupo = limpiar_dato(getattr(row, 'tipo_procedimiento', None))
        texto_servicio = limpiar_dato(getattr(row, 'descripcion_servicio', None)) # Leemos la descripción detallada
        
        # Llamamos a la función con 3 argumentos para que aprenda el nombre bonito
        proc_final = calcular_procedimiento(cups_raw, texto_grupo, texto_servicio)
        
        # FIRMA ÚNICA
        sig = (pid, d_sol_str, normalize_text(proc_final))
        if sig in existing_sigs: continue

        # TRADUCCIÓN DE ESTADOS
        estado_raw = getattr(row, 'estado_solicitud', None)
        estado_final = normalizar_estado_detallado(estado_raw)

        # OTROS DATOS
        eps_clean = normalizar_eps(getattr(row, 'entidad_aseguradora', None))
        agrupador_calc = obtener_agrupador(limpiar_dato(getattr(row, 'codigo_diagnostico', None)))
        prestador = limpiar_dato(getattr(row, 'prestador', None))
        tipo_caso = limpiar_dato(getattr(row, 'tipo_paciente', None))

        new_fs.append(FollowUp(
            patient_id=pid,
            tipo_procedimiento=proc_final,
            fecha_solicitud_cita=d_sol,
            estado_solicitud=estado_final,
            fecha_cita=parse_date(getattr(row, 'fecha_cita', None)),
            barrera=limpiar_dato(getattr(row, 'barrera', None)),
            observaciones=limpiar_dato(getattr(row, 'observaciones', None)),
            entidad_aseguradora=eps_clean,
            cups=cups_raw,
            ruta=limpiar_dato(getattr(row, 'ruta', None)),
            agrupador=agrupador_calc,
            prestador=prestador,
            tipo_paciente=tipo_caso,
            servicio=texto_servicio
        ))
        existing_sigs.add(sig)

    if new_fs:
        FollowUp.objects.bulk_create(new_fs, batch_size=500)

    return {"success": True, "registros": len(new_fs), "actualizados": len(update_ps)}

# --- 4. MÉTRICAS (Igual) ---
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
    eps_qs = FollowUp.objects.exclude(Q(entidad_aseguradora__isnull=True)|Q(entidad_aseguradora__exact='')).values('entidad_aseguradora').annotate(total=Count('id')).order_by('-total')[:10]
    e_labels = [str(x['entidad_aseguradora'])[:30] for x in eps_qs]
    e_values = [x['total'] for x in eps_qs]
    barrier_qs = FollowUp.objects.exclude(Q(barrera__isnull=True)|Q(barrera__exact='')).values('barrera').annotate(total=Count('id')).order_by('-total')[:10]
    b_labels = [str(x['barrera'])[:40] for x in barrier_qs]
    b_values = [x['total'] for x in barrier_qs]
    month_qs = FollowUp.objects.annotate(month=TruncMonth('fecha_solicitud_cita')).values('month').annotate(total=Count('id')).order_by('month')
    m_labels = [x['month'].strftime('%b %Y') for x in month_qs if x['month']]
    m_values = [x['total'] for x in month_qs if x['month']]
    return {'gender_labels': json.dumps(g_labels), 'gender_values': json.dumps(g_values), 'age_labels': json.dumps(list(rangos.keys())), 'age_values': json.dumps(list(rangos.values())), 'eps_labels': json.dumps(e_labels), 'eps_values': json.dumps(e_values), 'barrier_labels': json.dumps(b_labels), 'barrier_values': json.dumps(b_values), 'month_labels': json.dumps(m_labels), 'cnt_values': json.dumps(m_values)}