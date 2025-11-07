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
            
            # Top 5 diagnósticos
            diagnosticos = (
                df["diagnostico"]
                .value_counts()
                .head(5)
                .to_dict()
            )
            
            # Distribución por género
            genero = (
                df["genero"]
                .value_counts()
                .to_dict()
            )
            
            csv_data = {
                "top_diagnosticos_labels": json.dumps(list(diagnosticos.keys())),
                "top_diagnosticos_values": json.dumps(list(diagnosticos.values())),
                "genero_labels": json.dumps(list(genero.keys())),
                "genero_values": json.dumps(list(genero.values())),
            }
        except Exception as e:
            print(f"Error al procesar CSV: {e}")
    
    # 2. Obtener datos de la base de datos
    registros = FollowUp.objects.select_related('patient', 'treatment')
    
    # Aplicar filtros
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')

    if date_from and date_to:
        registros = registros.filter(session_date__range=[date_from, date_to])
    elif date_from:
        registros = registros.filter(session_date__gte=date_from)
    elif date_to:
        registros = registros.filter(session_date__lte=date_to)

    if status:
        if status == 'realizado':
            registros = registros.filter(completed=True)
        elif status in ['pendiente', 'en_gestion', 'por_gestionar', 'agendado']:
            registros = registros.filter(completed=False)

    if procedure:
        registros = registros.filter(treatment__tipo__icontains=procedure)

    # Calcular estadísticas
    total = registros.count()
    completados = registros.filter(completed=True).count()
    pendientes = registros.filter(completed=False).count()
    porcentaje_completado = round((completados / total) * 100, 1) if total else 0
    porcentaje_pendiente = 100 - porcentaje_completado

    estado_data = {
        "pendiente": pendientes,
        "completado": completados,
        "agendado": registros.filter(completed=False, interruption_reason='agendado').count(),
        "por_gestionar": registros.filter(completed=False, interruption_reason='por_gestionar').count()
    }

    procedimiento_data = list(
        registros.values('treatment__tipo')
        .annotate(total=Count('id'))
        .order_by('-total')
        .values('treatment__tipo', 'total')
    )

    # Combinar contexto
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

    # Agregar datos del CSV si existen
    if csv_data:
        context.update(csv_data)
    return render(request, 'followups.html', context)


# --- DETALLE DE PACIENTE ---
def followup_detail(request, patient_id):
    paciente = get_object_or_404(Patient, id=patient_id)

    seguimientos = FollowUp.objects.filter(patient=paciente).select_related('treatment').order_by('-session_date')

    total = seguimientos.count()
    ultima_actualizacion = seguimientos.aggregate(ultima=Max('session_date'))['ultima']

    context = {
        "paciente": paciente,
        "seguimientos": seguimientos,
        "resumen": {
            "total": total,
            "ultima_actualizacion": ultima_actualizacion,
        }
    }

    return render(request, "followup_detail.html", context)


# --- AGREGAR ---
def agregar_followup(request, pk):
    paciente = get_object_or_404(Patient, pk=pk)
    if request.method == 'POST':
        treatment_id = request.POST.get('treatment_id')
        session_date = request.POST.get('session_date')
        completed = 'completed' in request.POST
        reason = request.POST.get('interruption_reason')

        FollowUp.objects.create(
            patient=paciente,
            treatment_id=treatment_id,
            session_date=session_date,
            completed=completed,
            interruption_reason=reason
        )
        return redirect('detalle_paciente', pk=paciente.id)

    tratamientos = Treatment.objects.all()
    return render(request, 'followup_detail.html', {'paciente': paciente, 'tratamientos': tratamientos})


# --- EDITAR ---
def editar_followup(request, pk):
    seguimiento = get_object_or_404(FollowUp, pk=pk)
    if request.method == 'POST':
        seguimiento.treatment_id = request.POST.get('treatment_id')
        seguimiento.session_date = request.POST.get('session_date')
        seguimiento.completed = 'completed' in request.POST
        seguimiento.interruption_reason = request.POST.get('interruption_reason')
        seguimiento.save()
        return redirect('followup_detail', patient_id=seguimiento.patient.id)

    tratamientos = Treatment.objects.all()
    return render(request, 'editar_followup.html', {'seguimiento': seguimiento, 'tratamientos': tratamientos})


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
def analisis_institucional(request):
    """
    Lee el archivo procesado (processed_latest.csv), genera datos agregados
    para las gráficas institucionales.
    """
    csv_path = os.path.join(settings.MEDIA_ROOT, "uploads", "processed_latest.csv")
    if not os.path.exists(csv_path):
        return render(request, "analisis_institucional.html", {"error": "⚠️ No hay archivo cargado aún."})

    # --- Leer archivo ---
    df = pd.read_csv(csv_path)
    df.columns = _normalize_columns(df.columns)

    # --- Ajustar nombres según tus columnas ---
    # (en caso de variaciones como "estado_de_solicitud" o "estado_de__solicitud")
    posibles = df.columns
    print("Columnas detectadas:", posibles)

    # --- Grupos por diagnóstico ---
    diag_data = df["grupo_diagnostico"].value_counts().head(10)
    diag_labels = diag_data.index.tolist()
    diag_values = diag_data.values.tolist()

    # --- Distribución por género ---
    if "genero" in df.columns:
        gender_data = df["genero"].value_counts()
        gender_labels = gender_data.index.tolist()
        gender_values = gender_data.values.tolist()
    else:
        gender_labels, gender_values = [], []

    # --- Distribución por edad (agrupada) ---
    if "edad" in df.columns:
        df["edad"] = pd.to_numeric(df["edad"], errors="coerce")
        bins = [0, 20, 30, 40, 50, 60, 70, 80, 120]
        labels = ["<20", "20-29", "30-39", "40-49", "50-59", "60-69", "70-79", "80+"]
        df["rango_edad"] = pd.cut(df["edad"], bins=bins, labels=labels, right=False)
        age_data = df["rango_edad"].value_counts().sort_index()
        age_labels = age_data.index.tolist()
        age_values = age_data.values.tolist()
    else:
        age_labels, age_values = [], []

    # --- Estado de solicitud (Realizado / Pendiente) ---
    if "estado_de_solicitud" in df.columns:
        state_data = df["estado_de_solicitud"].value_counts()
    elif "estado_de__solicitud" in df.columns:
        state_data = df["estado_de__solicitud"].value_counts()
    else:
        state_data = pd.Series(dtype=int)
    state_labels = state_data.index.tolist()
    state_values = state_data.values.tolist()

    # --- Promedio de oportunidad ---
    if "oportunidad" in df.columns:
        df["oportunidad_num"] = pd.to_numeric(df["oportunidad"], errors="coerce")
        oportunidad_promedio = round(df["oportunidad_num"].mean(skipna=True), 2)
    else:
        oportunidad_promedio = None

    # --- Atenciones por mes ---
    if "mes_de_ordenamiento" in df.columns:
        month_data = df["mes_de_ordenamiento"].value_counts()
    else:
        month_data = pd.Series(dtype=int)
    month_labels = month_data.index.tolist()
    month_values = month_data.values.tolist()

    context = {
        "diag_labels": json.dumps(diag_labels),
        "diag_values": json.dumps(diag_values),
        "gender_labels": json.dumps(gender_labels),
        "gender_values": json.dumps(gender_values),
        "age_labels": json.dumps(age_labels),
        "age_values": json.dumps(age_values),
        "state_labels": json.dumps(state_labels),
        "state_values": json.dumps(state_values),
        "month_labels": json.dumps(month_labels),
        "month_values": json.dumps(month_values),
        "cnt_labels": json.dumps(month_labels),  # Use month data for count chart
        "cnt_values": json.dumps(month_values),  # Use month data for count chart
        "oportunidad_promedio": oportunidad_promedio,
    }

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