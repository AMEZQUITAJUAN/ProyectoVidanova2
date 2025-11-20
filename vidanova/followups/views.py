# followups/views.py
import os
import json
import pandas as pd
import unicodedata
from django.db.models import Count, Avg, Max, F, ExpressionWrapper, IntegerField
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_http_methods
from django.http import HttpResponse
from django.core.files.storage import FileSystemStorage

from .models import FollowUp
from patients.models import Patient
from treatments.models import Treatment
from .services import (
    load_dashboard_dataframe,
    compute_institutional_metrics,
    compute_request_status_from_db,
    compute_opportunity_by_procedure
)


# =============================================
# DASHBOARD PRINCIPAL - LIMPIO Y ESCALABLE
# =============================================
def followups(request):
    # Base queryset optimizado
    registros = FollowUp.objects.select_related('patient').order_by('-fecha_atencion')

    # === FILTROS ===
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')

    if date_from:
        registros = registros.filter(fecha_atencion__gte=date_from)
    if date_to:
        registros = registros.filter(fecha_atencion__lte=date_to)
    if status:
        registros = registros.filter(estado_solicitud__icontains=status.lower())
    if procedure:
        registros = registros.filter(tipo_procedimiento__icontains=procedure)

    # === Cálculo de días entre solicitud y cita (Django puro, sin bucles) ===
    registros = registros.annotate(
        dias_diff=ExpressionWrapper(
            F('fecha_cita') - F('fecha_solicitud_cita'),
            output_field=IntegerField()
        )
    )

    # === KPIs principales ===
    total = registros.count()
    completados = registros.filter(estado_solicitud__icontains='realizado').count()
    porcentaje_completado = round((completados / total) * 100, 1) if total else 0
    promedio_dias = registros.filter(dias_diff__gte=0).aggregate(Avg('dias_diff'))['dias_diff__avg']
    promedio_dias = round(promedio_dias, 1) if promedio_dias else None

    # === Barreras top 10 ===
    barreras_raw = registros.values('barrera').annotate(total=Count('id')).order_by('-total')[:10]
    barreras_labels = [b['barrera'] or 'Sin barrera' for b in barreras_raw]
    barreras_values = [b['total'] for b in barreras_raw]

    # === Estados y oportunidad (usando services con filtros aplicados) ===
    estado_mapeo = compute_request_status_from_db(registros)
    oportunidad = compute_opportunity_by_procedure(registros)

    # === Contexto final ===
       # === PAGINACIÓN (50 por página) ===
    from django.core.paginator import Paginator

    paginator = Paginator(registros, 50)  # 50 registros por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Contexto final (page_obj en vez de registros)
    context = {
        'page_obj': page_obj,           # ← para la tabla
        'registros': page_obj,          # ← para mantener compatibilidad con filtros
        'stats': {
            'total': total,
            'completados': completados,
            'pendientes': total - completados,
            'porcentaje_completado': porcentaje_completado,
            'promedio_dias': promedio_dias or '-',
        },
        'barreras_labels': json.dumps(barreras_labels),
        'barreras_values': json.dumps(barreras_values),
        'estado_procedimiento_labels': json.dumps(estado_mapeo['labels']),
        'estado_procedimiento_values': json.dumps(estado_mapeo['values']),
        'oportunidad_procedimiento_labels': json.dumps(oportunidad['procedimiento_labels']),
        'oportunidad_procedimiento_values': json.dumps(oportunidad['values']),
        'filtros': {
            'date_from': date_from or '',
            'date_to': date_to or '',
            'status': status or '',
            'procedure': procedure or '',
        }
    }

    return render(request, 'followups.html', context)


# =============================================
# RESTO DE VISTAS (sin cambios, solo limpias)
# =============================================
def followup_detail(request, patient_id):
    paciente = get_object_or_404(Patient, id=patient_id)
    seguimientos = FollowUp.objects.filter(patient=paciente).select_related('patient').order_by('-fecha_atencion')
    total = seguimientos.count()
    ultima_actualizacion = seguimientos.aggregate(ultima=Max('fecha_atencion'))['ultima']

    context = {
        "paciente": paciente,
        "seguimientos": seguimientos,
        "resumen": {"total": total, "ultima_actualizacion": ultima_actualizacion},
    }
    return render(request, "followup_detail.html", context)


def agregar_followup(request, patient_id):
    paciente = get_object_or_404(Patient, pk=patient_id)
    if request.method == 'POST':
        FollowUp.objects.create(
            patient=paciente,
            fecha_atencion=request.POST.get('fecha_atencion') or None,
            tipo_procedimiento=request.POST.get('tipo_procedimiento'),
            estado_solicitud=request.POST.get('estado_solicitud'),
            barrera=request.POST.get('barrera'),
            observaciones=request.POST.get('observaciones'),
            oportunidad=request.POST.get('oportunidad'),
        )
        return redirect('followup_detail', patient_id=paciente.id)
    return render(request, 'followup_detail.html', {'paciente': paciente})


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
    return render(request, 'editar_followup.html', {'seguimiento': seguimiento})


def eliminar_followup(request, pk):
    seguimiento = get_object_or_404(FollowUp, pk=pk)
    patient_id = seguimiento.patient.id
    seguimiento.delete()
    return redirect('followup_detail', patient_id=patient_id)


@require_http_methods(["GET", "POST"])
def cargar_datos(request):
    if request.method == 'POST' and request.FILES.get('archivo'):
        archivo = request.FILES['archivo']
        fs = FileSystemStorage(location=os.path.join(settings.MEDIA_ROOT, "uploads"))
        os.makedirs(fs.location, exist_ok=True)
        nombre = fs.save(archivo.name, archivo)
        ruta = os.path.join(fs.location, nombre)

        try:
            df = pd.read_excel(ruta) if nombre.endswith('.xlsx') else pd.read_csv(ruta)
            df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
            processed_path = os.path.join(fs.location, "processed_latest.csv")
            df.to_csv(processed_path, index=False, encoding='utf-8-sig')
            request.session['siisa_processed'] = processed_path
            return redirect('analisis_institucional')
        except Exception as e:
            return render(request, "cargar_datos.html", {"error": str(e)})

    return render(request, "cargar_datos.html")


def analisis_institucional(request):
    df, _ = load_dashboard_dataframe()
    if df is None:
        return render(request, "analisis_institucional.html", {"error": "No hay archivo cargado."})
    metrics = compute_institutional_metrics(df)
    metrics["rows"] = len(df)
    context = {k: json.dumps(v) if isinstance(v, (list, dict)) else v for k, v in metrics.items()}
    return render(request, "analisis_institucional.html", context)


def ver_datos_siisa(request):
    path = os.path.join(settings.MEDIA_ROOT, "uploads", "processed_latest.csv")
    if not os.path.exists(path):
        return HttpResponse("<h3 style='color:red;'>No se encontró el archivo procesado.</h3>")
    try:
        df = pd.read_csv(path)
        html = df.head(10).to_html(classes='table table-bordered', border=1)
        return HttpResponse(f"<h2>Vista previa</h2><p>{path}</p>{html}")
    except Exception as e:
        return HttpResponse(f"<h3>Error: {e}</h3>")