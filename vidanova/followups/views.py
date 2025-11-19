import os
import json
import pandas as pd
import unicodedata
from django.db.models import Max
from django.conf import settings
from django.conf.urls.static import static
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from .models import FollowUp
from patients.models import Patient
from treatments.models import Treatment
from django.db.models import Count
from django.core.files.storage import FileSystemStorage
from django.http import HttpResponse
from .services import load_dashboard_dataframe, compute_institutional_metrics, compute_request_status_from_db
from .services import load_dashboard_dataframe, compute_institutional_metrics, compute_request_status_from_db, compute_opportunity_by_procedure
# --- DASHBOARD PRINCIPAL ---
# --- DASHBOARD PRINCIPAL ---
def followups(request):

    registros = FollowUp.objects.select_related('patient')

    # -------------------------------
    # 1. Filtros
    # -------------------------------
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')

    if date_from and date_to:
        registros = registros.filter(fecha_atencion__range=[date_from, date_to])
    elif date_from:
        registros = registros.filter(fecha_atencion__gte=date_from)
    elif date_to:
        registros = registros.filter(fecha_atencion__lte=date_to)

    if status:
        status = status.lower()
        if status == "realizado":
            registros = registros.filter(estado_solicitud__icontains="realizado")
        elif status == "agendado":
            registros = registros.filter(estado_solicitud__icontains="agendado")
        else:
            registros = registros.filter(estado_solicitud__icontains=status)

    if procedure:
        registros = registros.filter(tipo_procedimiento__icontains=procedure)

    # -------------------------------
    # 2. Mapeo oficial de estados
    # -------------------------------
    ESTADOS_REALIZADO = ["realizado", "completado"]
    ESTADOS_AGENDADO = ["agendado", "en programación. prestador", "sin agenda"]
    ESTADOS_PENDIENTE = [
        "pendiente", "por gestionar", "en gestión", 
        "pendiente reporte", "en gestión interna"
    ]
    ESTADOS_EXCLUIR = ["fallecido", "no acepta", "diferido", "control mayor 3 meses"]

    def es_estado(followup, lista):
        estado = (followup.estado_solicitud or "").lower().strip()
        return any(e in estado for e in lista)

    # -------------------------------
    # 3. KPIs reales
    # -------------------------------
    total = registros.exclude(estado_solicitud__in=ESTADOS_EXCLUIR).count()

    completados = sum(es_estado(f, ESTADOS_REALIZADO) for f in registros)
    agendados = sum(es_estado(f, ESTADOS_AGENDADO) for f in registros)
    pendientes = sum(es_estado(f, ESTADOS_PENDIENTE) for f in registros)

    porcentaje_completado = round((completados / total) * 100, 1) if total else 0
    porcentaje_pendiente = 100 - porcentaje_completado

    # -------------------------------
    # 4. Promedio de días entre solicitud y cita
    # -------------------------------
    diferencias = []
    for f in registros:
        if f.fecha_solicitud_cita and f.fecha_cita:
            diff = (f.fecha_cita - f.fecha_solicitud_cita).days
            if diff >= 0:
                diferencias.append(diff)

    promedio_dias = round(sum(diferencias) / len(diferencias), 1) if diferencias else None

    # -------------------------------
    # 5. Barreras reales desde BD
    # -------------------------------
    barreras_raw = registros.values('barrera').annotate(total=Count('id')).order_by('-total')

    barreras_labels = [(b['barrera'] or "Sin dato") for b in barreras_raw]
    barreras_values = [b['total'] for b in barreras_raw]


    # -------------------------------
    # 6. Gráfica de oportunidad por procedimiento
    # -------------------------------


    # ---------------------------------------------------------
    # 1. CARGA DE CSV
    # ---------------------------------------------------------
    csv_path = os.path.join(settings.MEDIA_ROOT, "uploads", "processed_latest.csv")
    csv_data = {}

    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

            # Top diagnósticos (si aún los quieres)
            diag_col = None
            for c in ("diagnostico", "grupo_diagnostico", "diagnosticos"):
                if c in df.columns:
                    diag_col = c
                    break
            diagnosticos = df[diag_col].value_counts().head(5).to_dict() if diag_col else {}

            # Distribución por género
            genero = df["genero"].value_counts().to_dict() if "genero" in df.columns else {}

            csv_data = {
                "top_diagnosticos_labels": json.dumps(list(diagnosticos.keys())),
                "top_diagnosticos_values": json.dumps(list(diagnosticos.values())),
                "genero_labels": json.dumps(list(genero.keys())),
                "genero_values": json.dumps(list(genero.values())),
            }
        except Exception as e:
            print(f"Error al procesar CSV: {e}")

         # ---------------------------------------------------------
    # 2. CONSULTA BASE DE DATOS
    # ---------------------------------------------------------
    registros = FollowUp.objects.select_related('patient')

    # ---------------------------------------------------------
    # 3. FILTROS DEL DASHBOARD
    # ---------------------------------------------------------
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')

    if date_from and date_to:
        registros = registros.filter(fecha_atencion__range=[date_from, date_to])
    elif date_from:
        registros = registros.filter(fecha_atencion__gte=date_from)
    elif date_to:
        registros = registros.filter(fecha_atencion__lte=date_to)

    # Estado
    if status:
        if status.lower() == 'realizado':
            registros = registros.filter(estado_solicitud__icontains='realizado')
        else:
            registros = registros.exclude(estado_solicitud__icontains='realizado')

    # Procedimiento
    if procedure:
        registros = registros.filter(tipo_procedimiento__icontains=procedure)


    # ---------------------------------------------------------
    # 4. KPIs PRINCIPALES DEL DASHBOARD
    # ---------------------------------------------------------
    total = registros.count()
    completados = registros.filter(estado_solicitud__icontains='realizado').count()
    pendientes = total - completados
    porcentaje_completado = round((completados / total) * 100, 1) if total else 0
    porcentaje_pendiente = 100 - porcentaje_completado

    estado_data = {
        "pendiente": pendientes,
        "completado": completados,
        "agendado": registros.filter(estado_solicitud__icontains='agendado').count(),
        "por_gestionar": registros.filter(estado_solicitud__icontains='por_gestionar').count()
    }

    # ---------------------------------------------------------
    # 5. TOP DE PROCEDIMIENTOS
    # ---------------------------------------------------------
    procedimiento_data = list(
        registros.values('tipo_procedimiento')
        .annotate(total=Count('id'))
        .order_by('-total')
    )


    # ============================================================
    # ============ 🔥 NUEVO: BARRERAS DESDE LA BD ================
    # ============================================================
    # Aquí se cargan los labels y valores reales desde FollowUp

    barreras_raw = (
        registros.values("barrera")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    barreras_labels = [b["barrera"] or "Sin dato" for b in barreras_raw]
    barreras_values = [b["total"] for b in barreras_raw]


    # ============================================================
    # === 🔥 NUEVO: ESTADO DEL PROCEDIMIENTO (MAPEO OFICIAL) =====
    # ============================================================

    estado_mapeo = compute_request_status_from_db()
    # 👉 Aquí se generan:
    # estado_procedimiento_labels
    # estado_procedimiento_values


    # ============================================================
    # === 🔥 NUEVO: OPORTUNIDAD POR PROCEDIMIENTO ================
    # ============================================================

    oportunidad = compute_opportunity_by_procedure()
    # 👉 produce:
    # oportunidad_procedimiento_labels
    # oportunidad_procedimiento_values


    # ---------------------------------------------------------
    # 6. CONTEXTO PARA TEMPLATE HTML
    # ---------------------------------------------------------
    context = {
        "registros": registros,
        "stats": {
            "total": total,
            "completados": completados,
            "pendientes": pendientes,
            "porcentaje_completado": porcentaje_completado,
            "porcentaje_pendiente": porcentaje_pendiente,
        },
        "estado_data": json.dumps(estado_data),
        "procedimiento_data": json.dumps(procedimiento_data),

        # 🔥 NUEVOS DATOS PARA EL DASHBOARD
        "barreras_labels": json.dumps(barreras_labels),
        "barreras_values": json.dumps(barreras_values),
        "estado_procedimiento_labels": json.dumps(estado_mapeo["labels"]),
        "estado_procedimiento_values": json.dumps(estado_mapeo["values"]),
        "oportunidad_procedimiento_labels": json.dumps(oportunidad["procedimiento_labels"]),
        "oportunidad_procedimiento_values": json.dumps(oportunidad["procedimiento_values"]),

        "filtros": {
            "date_from": date_from or "",
            "date_to": date_to or "",
            "status": status or "",
            "procedure": procedure or "",
        }
    }

    if csv_data:
        context.update(csv_data)

    return render(request, 'followups.html', context)

# --- DETALLE DE PACIENTE ---
def followup_detail(request, patient_id):
    paciente = get_object_or_404(Patient, id=patient_id)
    seguimientos = FollowUp.objects.filter(patient=paciente).select_related('patient').order_by('-fecha_atencion')

    total = seguimientos.count()
    ultima_actualizacion = seguimientos.aggregate(ultima=Max('fecha_atencion'))['ultima']

    tratamientos = Treatment.objects.all()
    context = {
        "paciente": paciente,
        "seguimientos": seguimientos,
        "resumen": {
            "total": total,
            "ultima_actualizacion": ultima_actualizacion,
        },
        "tratamientos": tratamientos,
    }
    return render(request, "followup_detail.html", context)

# --- AGREGAR ---
def agregar_followup(request, patient_id):
    paciente = get_object_or_404(Patient, pk=patient_id)

    if request.method == 'POST':
        # Datos del formulario
        fecha_atencion = request.POST.get('fecha_atencion')
        tipo_procedimiento = request.POST.get('tipo_procedimiento')
        estado_solicitud = request.POST.get('estado_solicitud')
        barrera = request.POST.get('barrera')
        observaciones = request.POST.get('observaciones')
        oportunidad = request.POST.get('oportunidad')

        # Crear el nuevo seguimiento
        FollowUp.objects.create(
            patient=paciente,
            fecha_atencion=fecha_atencion or None,
            tipo_procedimiento=tipo_procedimiento,
            estado_solicitud=estado_solicitud,
            barrera=barrera,
            observaciones=observaciones,
            oportunidad=oportunidad,
        )

        return redirect('followup_detail', patient_id=paciente.id)

    # Campos que se pueden mostrar en el formulario
    context = {
        "paciente": paciente,
    }
    return render(request, 'followup_detail.html', context)


# --- EDITAR ---
def editar_followup(request, pk):
    seguimiento = get_object_or_404(FollowUp, pk=pk)

    if request.method == 'POST':
        seguimiento.fecha_atencion = request.POST.get('fecha_atencion') or None
        seguimiento.tipo_procedimiento = request.POST.get('tipo_procedimiento')
        seguimiento.estado_solicitud = request.POST.get('estado_solicitud')
        seguimiento.barrera = request.POST.get('barrera')
        seguimiento.observaciones = request.POST.get('observaciones')
        seguimiento.oportunidad = request.POST.get('oportunidad')
        seguimiento.save()

        return redirect('followup_detail', patient_id=seguimiento.patient.id)

    context = {
        "seguimiento": seguimiento,
    }
    return render(request, 'editar_followup.html', context)

# --- ELIMINAR ---
def eliminar_followup(request, pk):
    seguimiento = get_object_or_404(FollowUp, pk=pk)
    paciente_id = seguimiento.patient.id
    seguimiento.delete()
    return redirect('followup_detail', patient_id=paciente_id)

# --- UTIL: normalizar nombres de columnas (snake_case, sin espacios) ---
def _normalize_columns(cols):
    """Limpia acentos, mayúsculas y espacios de nombres de columna."""
    def clean(c):
        c = str(c).strip().lower()
        c = unicodedata.normalize('NFKD', c).encode('ascii', 'ignore').decode('utf-8')
        c = c.replace(" ", "_").replace("__", "_")
        return c
    return [clean(x) for x in cols]

# --- Vista: formulario para subir archivo ---
@require_http_methods(["GET","POST"])

def cargar_datos(request):
    """
    Sube un archivo CSV o XLSX con datos SIISA, lo convierte a CSV limpio y lo guarda en /media/uploads.
    Guarda la ruta en la sesión para el análisis posterior.
    """
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "uploads"))
        os.makedirs(fs.location, exist_ok=True)

        # Guardar archivo original
        nombre_archivo = fs.save(archivo.name, archivo)
        ruta_archivo = os.path.join(fs.location, nombre_archivo)

        # Leer según extensión
        try:
            if archivo.name.endswith('.xlsx'):
                df = pd.read_excel(ruta_archivo)
            elif archivo.name.endswith('.csv'):
                df = pd.read_csv(ruta_archivo)
            else:
                return render(request, "cargar_datos.html", {"error": "Formato no soportado (usa .csv o .xlsx)"})
        except Exception as e:
            return render(request, "cargar_datos.html", {"error": f"Error al leer el archivo: {e}"})

        # Normalizar columnas
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        # Guardar versión procesada
        processed_path = os.path.join(fs.location, "processed_latest.csv")
        df.to_csv(processed_path, index=False, encoding='utf-8-sig')

        # Guardar ruta en sesión
        request.session['siisa_processed'] = processed_path

        # Redirigir al análisis
        return redirect('analisis_institucional')

    return render(request, "cargar_datos.html")

# --- Vista: análisis / dashboard institucional con gráficas ---
from .services import load_dashboard_dataframe, compute_institutional_metrics

def analisis_institucional(request):
    df, csv_path = load_dashboard_dataframe()
    if df is None:
        return render(request, "analisis_institucional.html", {"error": "⚠️ No hay archivo cargado aún."})

    metrics = compute_institutional_metrics(df)
    # Añadimos el número de filas procesadas para la plantilla
    metrics["rows"] = len(df)

    # Serializar listas/objetos a JSON para la inyección segura en JS
    context = {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in metrics.items()}

    return render(request, "analisis_institucional.html", context)

urlpatterns = [
    # ...existing urls...
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

def ver_datos_siisa(request):
    """
    Muestra las primeras filas del archivo procesado (processed_latest.csv)
    para verificar las columnas y datos cargados.
    """
    csv_path = os.path.join(settings.MEDIA_ROOT, "uploads", "processed_latest.csv")

    if not os.path.exists(csv_path):
        return HttpResponse("<h3 style='color:red;'>⚠️ No se encontró processed_latest.csv en /media/uploads/</h3>")

    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        return HttpResponse(f"<h3 style='color:red;'>❌ Error al leer el archivo: {e}</h3>")

    # Muestra las 10 primeras filas
    html = df.head(10).to_html(classes='table table-bordered', border=1)
    html = f"""
    <h2>Vista previa del archivo procesado</h2>
    <p>Ruta: {csv_path}</p>
    {html}
    <hr>
    <a href='/seguimiento/analisis-institucional/'>Volver al análisis institucional</a>
    """
    return HttpResponse(html)