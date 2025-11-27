import os
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from django.http import HttpResponse

from .models import FollowUp
from .forms import FollowUpForm, UploadFileForm
from .services import (
    importar_archivo_masivo, 
    compute_request_status_from_db, 
    compute_opportunity_by_procedure,
    compute_barriers,
    compute_institutional_metrics_db
)

# --- 1. TABLERO PRINCIPAL (DASHBOARD) ---
def followup_dashboard(request):
    """
    Vista principal: Tablero de control + Listado con filtros y buscador.
    """
    # Queryset Base
    queryset = FollowUp.objects.select_related('patient').all().order_by('-fecha_solicitud_cita', '-id')

    # Captura de Filtros
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')
    q_search = request.GET.get('q')

    # Aplicación de Filtros
    if date_from: queryset = queryset.filter(fecha_solicitud_cita__gte=date_from)
    if date_to: queryset = queryset.filter(fecha_solicitud_cita__lte=date_to)
    
    if status: 
        queryset = queryset.filter(estado_solicitud__icontains=status)
    
    if procedure: 
        queryset = queryset.filter(tipo_procedimiento__icontains=procedure)
    
    # Buscador Global
    if q_search:
        queryset = queryset.filter(
            Q(patient__numero_documento__icontains=q_search) |
            Q(patient__nombre_1__icontains=q_search) |          
            Q(patient__apellido_1__icontains=q_search) |       
            Q(observaciones__icontains=q_search) |              
            Q(cups__icontains=q_search)
        )

    # Cálculo de KPIs Operativos
    kpi_status = compute_request_status_from_db(queryset)
    kpi_procedure = compute_opportunity_by_procedure(queryset)
    kpi_barriers = compute_barriers(queryset)

    # Stats rápidas
    realizados = queryset.filter(estado_solicitud__icontains='REALIZADO', fecha_cita__isnull=False, fecha_solicitud_cita__isnull=False)
    dias_list = []
    for r in realizados:
        if r.dias_diff is not None and r.dias_diff >= 0: # Ignoramos errores negativos para el promedio
            dias_list.append(r.dias_diff)
            
    promedio = round(sum(dias_list) / len(dias_list), 1) if dias_list else 0

    total_registros = queryset.count()
    pct_pendientes = 0
    if total_registros > 0:
        pct_pendientes = round((kpi_status['pendientes'] / total_registros) * 100, 1)

    stats = {
        'total': total_registros,
        'completados': kpi_status['completados'],
        'pendientes': kpi_status['pendientes'],
        'porcentaje_completado': kpi_status['porcentaje_completado'],
        'porcentaje_pendientes': pct_pendientes,
        'promedio_dias': promedio
    }

    # Paginación
    per_page = request.GET.get('per_page', 25)
    try: per_page = int(per_page)
    except ValueError: per_page = 25

    paginator = Paginator(queryset, per_page)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'per_page': per_page, 
        'page_obj': page_obj,
        'filtros': request.GET,
        'stats': stats,
        'estado_procedimiento_labels': kpi_status['labels'],
        'estado_procedimiento_values': kpi_status['values'],
        'oportunidad_procedimiento_labels': kpi_procedure['procedimiento_labels'],
        'oportunidad_procedimiento_values': kpi_procedure['values'],
        'barreras_labels': kpi_barriers['labels'],
        'barreras_values': kpi_barriers['values'],
    }
    return render(request, 'followups.html', context)

# --- 2. IMPORTACIÓN DE DATOS (LA QUE FALTABA) ---
def importar_datos(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            fs = FileSystemStorage()
            filename = fs.save(archivo.name, archivo)
            file_path = fs.path(filename)
            try:
                resultado = importar_archivo_masivo(file_path)
                
                if resultado.get('success'):
                    msg = f"Carga completada. Nuevos: {resultado.get('registros')}, Actualizados: {resultado.get('actualizados')}"
                    messages.success(request, msg)
                else:
                    messages.error(request, f"Error: {resultado.get('error')}")
            except Exception as e:
                messages.error(request, f"Error crítico: {str(e)}")
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
            return redirect('followup_dashboard')
    else:
        form = UploadFileForm()
    return render(request, 'cargar_datos.html', {'form': form})

# --- 3. EXPORTACIÓN EXCEL ---
def exportar_excel(request):
    """
    Exporta a Excel aplicando los mismos filtros de la vista.
    """
    queryset = FollowUp.objects.select_related('patient').all().order_by('-fecha_solicitud_cita')
    
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')
    q_search = request.GET.get('q')

    if date_from: queryset = queryset.filter(fecha_solicitud_cita__gte=date_from)
    if date_to: queryset = queryset.filter(fecha_solicitud_cita__lte=date_to)
    if status: queryset = queryset.filter(estado_solicitud__icontains=status)
    if procedure: queryset = queryset.filter(tipo_procedimiento__icontains=procedure)
    
    if q_search:
        queryset = queryset.filter(
            Q(patient__numero_documento__icontains=q_search) | 
            Q(patient__nombre_1__icontains=q_search) |
            Q(patient__apellido_1__icontains=q_search) |
            Q(observaciones__icontains=q_search) |
            Q(cups__icontains=q_search)
        )

    data = []
    for f in queryset:
        data.append({
            'Documento': f.patient.numero_documento,
            'Paciente': f.patient.nombre_completo,
            'Edad': f.patient.edad,
            'Género': f.patient.genero,
            'Aseguradora': f.entidad_aseguradora,
            'Tipo Procedimiento': f.tipo_procedimiento,
            'CUPS': f.cups,
            'Estado': f.estado_solicitud,
            'Fecha Solicitud': f.fecha_solicitud_cita,
            'Fecha Cita': f.fecha_cita,
            'Días Gestión': f.dias_diff,
            'Barrera': f.barrera,
            'Observaciones': f.observaciones,
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="Reporte_Seguimiento_Vidanova.xlsx"'
    df.to_excel(response, index=False, engine='openpyxl')
    return response

# --- 4. ANÁLISIS GERENCIAL ---
def analisis_institucional(request):
    metrics = compute_institutional_metrics_db()
    total_rows = FollowUp.objects.count()
    context = {
        **metrics,
        'rows': total_rows
    }
    return render(request, 'analisis_institucional.html', context)

# --- 5. CRUD (DETALLES, EDITAR, ELIMINAR) ---

def followup_detail(request, pk):
    followup = get_object_or_404(FollowUp, pk=pk)
    return render(request, 'followup_detail.html', {'followup': followup})

def editar_followup(request, pk):
    followup = get_object_or_404(FollowUp, pk=pk)
    if request.method == 'POST':
        form = FollowUpForm(request.POST, instance=followup)
        if form.is_valid():
            form.save()
            messages.success(request, f"Caso de {followup.patient.nombre_completo} actualizado.")
            return redirect('followup_dashboard')
    else:
        form = FollowUpForm(instance=followup)
    
    return render(request, 'followup_form.html', {
        'form': form, 
        'title': 'Editar Seguimiento',
        'patient': followup.patient
    })

def agregar_followup(request, patient_id):
    from patients.models import Patient
    patient = get_object_or_404(Patient, pk=patient_id)
    if request.method == 'POST':
        form = FollowUpForm(request.POST)
        if form.is_valid():
            nuevo = form.save(commit=False)
            nuevo.patient = patient
            nuevo.save()
            messages.success(request, "Nuevo seguimiento creado.")
            return redirect('followup_dashboard')
    else:
        form = FollowUpForm(initial={'patient': patient})

    return render(request, 'followup_form.html', {
        'form': form, 
        'title': 'Nuevo Seguimiento', 
        'patient': patient
    })

def eliminar_followup(request, pk):
    followup = get_object_or_404(FollowUp, pk=pk)
    if request.method == 'POST':
        followup.delete()
        messages.success(request, "Registro eliminado.")
        return redirect('followup_dashboard')
    return render(request, 'followup_confirm_delete.html', {'followup': followup})

def ver_datos_siisa(request):
    return redirect('followup_dashboard')