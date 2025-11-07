import os
import json
import pandas as pd
from django.db.models import Max
from django.conf import settings
from django.core.files.storage import default_storage
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.urls import reverse
from .models import FollowUp
from patients.models import Patient
from treatments.models import Treatment
from django.db.models import Count
from django.core.files.storage import FileSystemStorage

# --- DASHBOARD PRINCIPAL ---
def followups(request):
    registros = FollowUp.objects.select_related('patient', 'treatment')

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

    total = registros.count()
    completados = registros.filter(completed=True).count()
    pendientes = registros.filter(completed=False).count()
    porcentaje_completado = round((completados / total) * 100, 1) if total else 0
    porcentaje_pendiente = 100 - porcentaje_completado

    estado_data = {"pendiente": pendientes, "completado": completados, "agendado": 0, "por_gestionar": 0}
    procedimiento_data = list(
        registros.values('treatment__tipo')
        .annotate(total=Count('id'))
        .order_by('treatment__tipo')
    )

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
    def norm(c):
        c = str(c).strip().lower()
        c = c.replace(' ', '_').replace('-', '_').replace('.', '').replace('/', '_')
        # eliminar caracteres especiales
        return ''.join(ch for ch in c if ch.isalnum() or ch == '_')
    return [norm(c) for c in cols]

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
    Lee el archivo más reciente cargado (session o media/uploads/processed_latest.csv),
    genera datos estadísticos y los pasa al template (para graficar con Chart.js).
    """
    csv_path = request.session.get('siisa_processed') or os.path.join(settings.MEDIA_ROOT, "uploads", "processed_latest.csv")
    if not os.path.exists(csv_path):
        return render(request, "analisis_institucional.html", {"error": "No hay datos procesados. Sube un archivo desde 'Cargar datos'."})

    # --- Cargar el archivo ---
    df = pd.read_csv(csv_path)
    df.columns = _normalize_columns(df.columns)

    # --- Renombrar columnas importantes si existen ---
    col_map = {
        "grupo_diagnostico": "grupo_diagnostico",
        "diagnostico": "diagnostico",
        "genero": "genero",
        "edad": "edad",
        "estado_de_solicitud": "estado_de_solicitud",
        "oportunidad": "oportunidad",
        "mes_de_ordenamiento": "mes_orden",
        "semana_de_ordenamiento": "semana_orden"
    }
    for k, v in col_map.items():
        if k not in df.columns:
            # intenta buscar por nombre parcial (más flexible)
            match = [c for c in df.columns if k.split("_")[0] in c]
            if match:
                df[v] = df[match[0]]
        else:
            df[v] = df[k]

    # --- Limpieza general ---
    df = df.dropna(subset=["grupo_diagnostico"], how="any")

    # --- Gráfica 1: Pacientes por grupo diagnóstico ---
    diag_data = df["grupo_diagnostico"].value_counts().sort_values(ascending=False)
    diag_labels = list(diag_data.index)
    diag_values = list(diag_data.values)

    # --- Gráfica 2: Distribución por género ---
    gender_data = df["genero"].value_counts()
    gender_labels = list(gender_data.index)
    gender_values = list(gender_data.values)

    # --- Gráfica 3: Rango de edades ---
    df["edad"] = pd.to_numeric(df["edad"], errors="coerce")
    df["grupo_edad"] = pd.cut(df["edad"], bins=[0,18,30,45,60,75,100],
                              labels=["0-18","19-30","31-45","46-60","61-75","+75"])
    age_data = df["grupo_edad"].value_counts().sort_index()
    age_labels = list(age_data.index.astype(str))
    age_values = list(age_data.values)

    # --- Gráfica 4: Estado de solicitud (Realizado vs Pendiente) ---
    state_data = df["estado_de_solicitud"].value_counts()
    state_labels = list(state_data.index)
    state_values = list(state_data.values)

    # --- Gráfica 5: Oportunidad promedio ---
    df["oportunidad"] = pd.to_numeric(df["oportunidad"], errors="coerce")
    oportunidad_prom = round(df["oportunidad"].mean(skipna=True), 1)

    # --- Gráfica 6: Actividad por mes ---
    month_data = df["mes_orden"].value_counts().sort_index()
    month_labels = list(month_data.index)
    month_values = list(month_data.values)

    # --- Gráfica 7: Actividad por semana ---
    week_data = df["semana_orden"].value_counts().sort_index()
    week_labels = list(week_data.index)
    week_values = list(week_data.values)

    context = {
        "diag_labels": diag_labels,
        "diag_values": diag_values,
        "gender_labels": gender_labels,
        "gender_values": gender_values,
        "age_labels": age_labels,
        "age_values": age_values,
        "state_labels": state_labels,
        "state_values": state_values,
        "month_labels": month_labels,
        "month_values": month_values,
        "week_labels": week_labels,
        "week_values": week_values,
        "oportunidad_prom": oportunidad_prom,
    }

    return render(request, "analisis_institucional.html", context)

