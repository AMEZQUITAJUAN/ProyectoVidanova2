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

def followup_dashboard(request):
    """
    Vista principal: Tablero de control + Listado con filtros y buscador.
    """
    # 1. Queryset Base (Optimizado)
    queryset = FollowUp.objects.select_related('patient').all().order_by('-fecha_solicitud_cita', '-id')

    # 2. Captura de Filtros
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')
    q_search = request.GET.get('q')

    # 3. Aplicación de Filtros (CORREGIDA 🔥)
    if date_from: 
        queryset = queryset.filter(fecha_solicitud_cita__gte=date_from)
    if date_to: 
        queryset = queryset.filter(fecha_solicitud_cita__lte=date_to)
    
    if status: 
        # Usamos icontains por si acaso hay variaciones (Pendiente vs PENDIENTE)
        queryset = queryset.filter(estado_solicitud__icontains=status)
    
    if procedure: 
        # 🔥 AQUÍ ESTABA EL ERROR: Cambiamos exact match por __icontains
        # Ahora "CONSULTA" encontrará "CONSULTA DE CONTROL..."
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

    # 4. Cálculo de KPIs (Mantenemos igual)
    kpi_status = compute_request_status_from_db(queryset)
    kpi_procedure = compute_opportunity_by_procedure(queryset)
    kpi_barriers = compute_barriers(queryset)

    # Stats rápidas
    realizados = queryset.filter(estado_solicitud__icontains='REALIZADO', fecha_cita__isnull=False, fecha_solicitud_cita__isnull=False)
    
    dias_list = []
    for r in realizados:
        if r.dias_diff is not None:
            dias_list.append(r.dias_diff)
            
    promedio = round(sum(dias_list) / len(dias_list), 1) if dias_list else 0

    total_registros = queryset.count()
    
    # Cálculo seguro del porcentaje de pendientes (evitando división por cero)
    pct_pendientes = 0
    if total_registros > 0:
        pct_pendientes = round((kpi_status['pendientes'] / total_registros) * 100, 1)

    stats = {
        'total': queryset.count(),
        'completados': kpi_status['completados'],
        'pendientes': kpi_status['pendientes'],
        'porcentaje_completado': kpi_status['porcentaje_completado'],
        'porcentaje_pendientes': pct_pendientes,
        'promedio_dias': promedio
    }

    # 5. PAGINACIÓN
    per_page = request.GET.get('per_page', 25)
    try:
        per_page = int(per_page)
    except ValueError:
        per_page = 25

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
    



def exportar_excel(request):
    """
    Exporta a Excel aplicando los mismos filtros de la vista.
    """
    queryset = FollowUp.objects.select_related('patient').all().order_by('-fecha_solicitud_cita')
    
    # Filtros repetidos (idealmente extraer a una función helper, pero lo dejamos así por simplicidad)
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')
    q_search = request.GET.get('q')

    if date_from: queryset = queryset.filter(fecha_solicitud_cita__gte=date_from)
    if date_to: queryset = queryset.filter(fecha_solicitud_cita__lte=date_to)
    if status: queryset = queryset.filter(estado_solicitud=status)
    if procedure: queryset = queryset.filter(tipo_procedimiento=procedure)
    
    if q_search:
        queryset = queryset.filter(
            Q(patient__numero_documento__icontains=q_search) | 
            Q(patient__nombre_1__icontains=q_search) |
            Q(patient__apellido_1__icontains=q_search) |
            Q(observaciones__icontains=q_search)
        )

    # Construir data
    data = []
    for f in queryset:
        data.append({
            'Documento': f.patient.numero_documento,
            'Paciente': f.patient.nombre, # Aquí SÍ podemos usar la propiedad porque es Python, no SQL
            'Tipo Procedimiento': f.tipo_procedimiento,
            'Estado': f.estado_solicitud,
            'Barrera': f.barrera,
            'Fecha Solicitud': f.fecha_solicitud_cita,
            'Fecha Cita': f.fecha_cita,
            'Días Espera': f.dias_diff,
            'Observaciones': f.observaciones,
            'CUPS': f.cups,
            'Servicio': f.servicio,
        })

    df = pd.DataFrame(data)
    response = HttpResponse(content_type='application/vnd.ms-excel')
    response['Content-Disposition'] = 'attachment; filename="Reporte_Seguimiento.xlsx"'
    df.to_excel(response, index=False, engine='openpyxl')
    return response

# --- VISTAS DE CARGA Y GESTIÓN (Sin cambios mayores) ---

def importar_datos(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            fs = FileSystemStorage()
            filename = fs.save(archivo.name, archivo)
            file_path = fs.path(filename)
            try:
                # Usamos el servicio de services.py
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

def editar_followup(request, pk):
    followup = get_object_or_404(FollowUp, pk=pk)
    if request.method == 'POST':
        form = FollowUpForm(request.POST, instance=followup)
        if form.is_valid():
            form.save()
            messages.success(request, f"Caso de {followup.patient.nombre} actualizado.")
            return redirect('followup_dashboard')
    else:
        form = FollowUpForm(instance=followup)
    
    # Contexto para autocompletar en frontend si lo tuvieras
    servicios_existentes = FollowUp.objects.values_list('servicio', flat=True).distinct()
    
    return render(request, 'followup_form.html', {
        'form': form, 
        'title': 'Editar Seguimiento',
        'patient': followup.patient,
        'servicios_list': servicios_existentes
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

def followup_detail(request, pk):
    followup = get_object_or_404(FollowUp, pk=pk)
    return render(request, 'followup_detail.html', {'followup': followup})

def analisis_institucional(request):
    metrics = compute_institutional_metrics_db()
    return render(request, 'analisis_institucional.html', {'metrics': metrics})

def ver_datos_siisa(request):
    return redirect('followup_dashboard')