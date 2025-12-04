import os
import pandas as pd
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import HttpResponse
from django.utils import timezone

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
@login_required
def followup_dashboard(request):
    """
    Vista principal: Tablero de control + Listado con filtros y buscador.
    """
    # 1. Queryset Base
    queryset = FollowUp.objects.select_related('patient').all().order_by('-fecha_solicitud_cita', '-id')

    # 2. Captura de Filtros
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    status = request.GET.get('status')
    procedure = request.GET.get('procedure')
    eps = request.GET.get('eps')
    barrier = request.GET.get('barrier')
    q_search = request.GET.get('q')

    # 3. Aplicación de Filtros
    if date_from: queryset = queryset.filter(fecha_solicitud_cita__gte=date_from)
    if date_to: queryset = queryset.filter(fecha_solicitud_cita__lte=date_to)
    
    if status: queryset = queryset.filter(estado_solicitud__icontains=status)
    if procedure: queryset = queryset.filter(tipo_procedimiento__icontains=procedure)
    
    # Filtros Exactos
    if eps: queryset = queryset.filter(entidad_aseguradora=eps)
    if barrier: queryset = queryset.filter(barrera=barrier)
    
    # Buscador Global
    if q_search:
        queryset = queryset.filter(
            Q(patient__numero_documento__icontains=q_search) |
            Q(patient__nombre_1__icontains=q_search) |          
            Q(patient__apellido_1__icontains=q_search) |       
            Q(observaciones__icontains=q_search) |              
            Q(cups__icontains=q_search)
        )

    # 4. Obtener Opciones para los Selectores (Distinct Values)
    eps_options = FollowUp.objects.exclude(entidad_aseguradora__isnull=True)\
        .exclude(entidad_aseguradora='').values_list('entidad_aseguradora', flat=True).distinct().order_by('entidad_aseguradora')
        
    barrier_options = FollowUp.objects.exclude(barrera__isnull=True)\
        .exclude(barrera='').values_list('barrera', flat=True).distinct().order_by('barrera')

    # 5. KPIs y Estadísticas Avanzadas
    # A. Total GLOBAL (Sin filtros) para calcular el porcentaje real
    grand_total = FollowUp.objects.count()

    # B. Total FILTRADO (El que ve el usuario)
    total_registros_filtrados = queryset.count()

    # C. Cálculo de Porcentaje Global
    pct_global = 0
    if grand_total > 0:
        pct_global = round((total_registros_filtrados / grand_total) * 100, 1)

    # D. Cálculo de Pendientes (sobre lo filtrado)
    kpi_status = compute_request_status_from_db(queryset)
    kpi_procedure = compute_opportunity_by_procedure(queryset)
    kpi_barriers = compute_barriers(queryset)

    pct_pendientes = 0
    if total_registros_filtrados > 0:
        pct_pendientes = round((kpi_status['pendientes'] / total_registros_filtrados) * 100, 1)

    # E. Cálculo de Promedio Días (sobre lo filtrado)
    realizados = queryset.filter(estado_solicitud__icontains='REALIZADO', fecha_cita__isnull=False, fecha_solicitud_cita__isnull=False)
    dias_list = [r.dias_diff for r in realizados if r.dias_diff is not None and r.dias_diff >= 0]
    promedio = round(sum(dias_list) / len(dias_list), 1) if dias_list else 0

    # Diccionario Final de Estadísticas
    stats = {
        'total': total_registros_filtrados,   # Número grande (Filtrado)
        'pct_global': pct_global,             # Porcentaje vs Base Total
        'grand_total': grand_total,           
        'completados': kpi_status['completados'],
        'pendientes': kpi_status['pendientes'],
        'porcentaje_completado': kpi_status['porcentaje_completado'],
        'porcentaje_pendientes': pct_pendientes,
        'promedio_dias': promedio
    }

    # 6. Paginación
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
        # Listas para Dropdowns
        'eps_options': eps_options,       
        'barrier_options': barrier_options,
        # Gráficas
        'estado_procedimiento_labels': kpi_status['labels'],
        'estado_procedimiento_values': kpi_status['values'],
        'oportunidad_procedimiento_labels': kpi_procedure['procedimiento_labels'],
        'oportunidad_procedimiento_values': kpi_procedure['values'],
        'barreras_labels': kpi_barriers['labels'],
        'barreras_values': kpi_barriers['values'],
    }
    return render(request, 'followups.html', context)

# --- 2. IMPORTACIÓN DE DATOS (LA QUE FALTABA) ---
@login_required
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
            # --- LÓGICA DE BITÁCORA ---
            nueva_nota = form.cleaned_data.get('nueva_observacion')
            
            if nueva_nota:
                # 1. Obtenemos datos de auditoría
                usuario = request.user.username.title() # Ej: "Admin"
                ahora = timezone.now().strftime("%d/%m/%Y %H:%M") # Ej: 03/12/2025 10:30
                
                # 2. Formateamos la entrada: [Fecha Usuario]: Texto
                entrada_bitacora = f"[{ahora} - {usuario}]: {nueva_nota}"
                
                # 3. Concatenamos (Lo nuevo arriba)
                historial_previo = followup.observaciones or ""
                # Agregamos salto de línea si ya había historia
                if historial_previo:
                    followup.observaciones = f"{entrada_bitacora}\n{historial_previo}"
                else:
                    followup.observaciones = entrada_bitacora
            
            # Guardamos (Django guarda el campo observaciones modificado automáticamente)
            form.save()
            
            messages.success(request, f"Gestión de {followup.patient.nombre_completo} registrada.")
            return redirect('followup_dashboard')
    else:
        form = FollowUpForm(instance=followup)
    
    return render(request, 'followup_form.html', {
        'form': form, 
        'title': 'Gestionar Caso',
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
# --- 6. ACCIONES MASIVAS (BULK ACTIONS) ---

@login_required
def actualizacion_masiva(request):
    """
    Procesa acciones masivas: Estado + Nota en Bitácora + Fecha Cita.
    """
    if request.method == 'POST':
        # 1. Obtener datos del Modal
        # IDs viene como un string separado por comas desde el JS: "1,4,5"
        ids_str = request.POST.get('selected_ids', '')
        
        nuevo_estado = request.POST.get('bulk_status')
        nueva_nota = request.POST.get('bulk_observation')
        nueva_fecha_cita = request.POST.get('bulk_date')
        
        if not ids_str:
            messages.warning(request, "⚠️ No se seleccionaron registros.")
            return redirect('followup_dashboard')

        ids_list = ids_str.split(',')
        registros = FollowUp.objects.filter(id__in=ids_list)
        count = registros.count()
        updated_objs = []

        # Datos de auditoría
        usuario = request.user.username.title()
        ahora = timezone.now().strftime("%d/%m/%Y %H:%M")

        # 2. Iterar y modificar en memoria (Para la bitácora)
        for r in registros:
            cambios_realizados = False

            # A. Cambio de Estado
            if nuevo_estado:
                r.estado_solicitud = nuevo_estado
                cambios_realizados = True

            # B. Cambio de Fecha
            if nueva_fecha_cita:
                r.fecha_cita = nueva_fecha_cita
                cambios_realizados = True

            # C. Inyección en Bitácora (Append)
            if nueva_nota:
                entrada = f"[{ahora} - {usuario} - MASIVO]: {nueva_nota}"
                historial_previo = r.observaciones or ""
                r.observaciones = f"{entrada}\n{historial_previo}"
                cambios_realizados = True
            
            if cambios_realizados:
                updated_objs.append(r)

        # 3. Guardado Eficiente (Bulk Update)
        if updated_objs:
            fields_to_update = ['observaciones']
            if nuevo_estado: fields_to_update.append('estado_solicitud')
            if nueva_fecha_cita: fields_to_update.append('fecha_cita')
            
            FollowUp.objects.bulk_update(updated_objs, fields_to_update)
            messages.success(request, f"✅ Se gestionaron {count} pacientes correctamente.")
        else:
            messages.info(request, "No se aplicaron cambios.")
            
    return redirect('followup_dashboard')