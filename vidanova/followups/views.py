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
def followups(request):
    """
    Dashboard principal que combina datos del CSV y de la base de datos
    """
    # 1. Cargar datos del CSV si existe
    csv_path = os.path.join(settings.MEDIA_ROOT, "uploads", "processed_latest.csv")
    csv_data = {}
    
    if os.path.exists(csv_path):
        try:
            df = pd.read_csv(csv_path)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

            # Top 5 diagnósticos (soportamos varias posibles columnas de diagnóstico)
            diag_col = None
            for c in ("diagnostico", "grupo_diagnostico", "diagnosticos"):
                if c in df.columns:
                    diag_col = c
                    break
            if diag_col:
                diagnosticos = df[diag_col].value_counts().head(5).to_dict()
            else:
                diagnosticos = {}

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
    
    # 2. Obtener datos de la base de datos
    registros = FollowUp.objects.select_related('patient')
    
    # --- Filtros ---
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')

    # Filtro de fechas (usa fecha_atencion en lugar de session_date)
    if date_from and date_to:
        registros = registros.filter(fecha_atencion__range=[date_from, date_to])
    elif date_from:
        registros = registros.filter(fecha_atencion__gte=date_from)
    elif date_to:
        registros = registros.filter(fecha_atencion__lte=date_to)

    # Filtro de estado (usa estado_solicitud)
    if status:
        if status.lower() == 'realizado':
            registros = registros.filter(estado_solicitud__icontains='realizado')
        elif status.lower() in ['pendiente', 'en_gestion', 'por_gestionar', 'agendado']:
            registros = registros.exclude(estado_solicitud__icontains='realizado')

    # Filtro por tipo de procedimiento
    if procedure:
        registros = registros.filter(tipo_procedimiento__icontains=procedure)

    # --- Estadísticas ---
    total = registros.count()
    completados = registros.filter(estado_solicitud__icontains='realizado').count()
    pendientes = total - completados
    porcentaje_completado = round((completados / total) * 100, 1) if total else 0
    porcentaje_pendiente = 100 - porcentaje_completado

   # --- Datos para las gráficas ---
    estado_data = {
        "pendiente": pendientes,
        "completado": completados,
        "agendado": registros.filter(estado_solicitud__icontains='agendado').count(),
        "por_gestionar": registros.filter(estado_solicitud__icontains='por_gestionar').count()
    }

    procedimiento_data = list(
        registros.values('tipo_procedimiento')
        .annotate(total=Count('id'))
        .order_by('-total')
    )



    # --- Contexto para el template ---
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
        "filtros": {
            "date_from": date_from or "",
            "date_to": date_to or "",
            "status": status or "",
            "procedure": procedure or "",
        }
    }

    # Obtener datos de oportunidad por procedimiento
    oportunidad_procedimiento = compute_opportunity_by_procedure()
    context["oportunidad_procedimiento_labels"] = json.dumps(oportunidad_procedimiento["procedimiento_labels"])
    context["oportunidad_procedimiento_values"] = json.dumps(oportunidad_procedimiento["procedimiento_values"])

    # Agregar datos del CSV si existen
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