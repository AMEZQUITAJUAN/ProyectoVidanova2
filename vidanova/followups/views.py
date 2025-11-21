# followups/views.py
import os
from django.shortcuts import render, redirect, get_object_or_404
from django.core.files.storage import FileSystemStorage
from django.core.paginator import Paginator
from django.contrib import messages
from django.db.models import Q
from django.conf import settings

from .models import FollowUp
from .forms import FollowUpForm, UploadFileForm
from .services import (
    importar_archivo_masivo, 
    compute_request_status_from_db, 
    compute_opportunity_by_procedure,
    compute_barriers
)

def followup_dashboard(request):
    # 1. Queryset Base (Optimizado)
    queryset = FollowUp.objects.select_related('patient').all().order_by('-fecha_solicitud_cita')

    # 2. Filtros
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
            Q(patient__nombre__icontains=q_search) | 
            Q(patient__documento__icontains=q_search)
        )

    # 3. KPIs (Calculados sobre los datos filtrados)
    kpi_status = compute_request_status_from_db(queryset)
    kpi_procedure = compute_opportunity_by_procedure(queryset)
    kpi_barriers = compute_barriers(queryset)

    # Stats rápidas
    realizados = queryset.filter(estado_solicitud='REALIZADO').exclude(fecha_cita__isnull=True, fecha_solicitud_cita__isnull=True)
    dias_list = [r.dias_diff for r in realizados if r.dias_diff is not None]
    promedio = round(sum(dias_list) / len(dias_list), 1) if dias_list else 0

    stats = {
        'total': queryset.count(),
        'completados': kpi_status['completados'],
        'pendientes': kpi_status['pendientes'],
        'porcentaje_completado': kpi_status['porcentaje_completado'],
        'promedio_dias': promedio
    }

    # 4. Paginación
    paginator = Paginator(queryset, 20) # 20 por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
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

def importar_datos(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            archivo = request.FILES['archivo']
            fs = FileSystemStorage()
            
            # Guardar archivo temporalmente
            filename = fs.save(archivo.name, archivo)
            file_path = fs.path(filename)
            
            try:
                # LLAMADA AL SERVICIO MAESTRO
                resultado = importar_archivo_masivo(file_path)
                
                if resultado.get('success'):
                    msg = f"Proceso completado. {resultado.get('mensaje', '')} (Total nuevos: {resultado.get('registros')})"
                    messages.success(request, msg)
                else:
                    messages.error(request, f"Error en el archivo: {resultado.get('error')}")
            
            except Exception as e:
                messages.error(request, f"Error interno al procesar: {str(e)}")
            finally:
                # Limpieza: Borrar archivo temporal
                if os.path.exists(file_path):
                    os.remove(file_path)
            
            return redirect('followup_dashboard')
    else:
        form = UploadFileForm()
    
    return render(request, 'cargar_datos.html', {'form': form})
# --- PEGAR AL FINAL DE followups/views.py ---

def analisis_institucional(request):
    """
    Vista para el dashboard basado en CSV institucional.
    """
    # Usamos el servicio que ya tienes para cargar datos procesados
    from .services import load_dashboard_dataframe, compute_institutional_metrics
    
    df, path = load_dashboard_dataframe()
    metrics = {}
    if df is not None:
        metrics = compute_institutional_metrics(df)
    
    # Si no tienes el template analisis_institucional.html, redirige al dashboard temporalmente
    return render(request, 'analisis_institucional.html', {'metrics': metrics})

def followup_detail(request, pk):
    """
    Vista de detalle de un paciente específico.
    """
    followup = get_object_or_404(FollowUp, pk=pk)
    return render(request, 'followup_detail.html', {'followup': followup})

def agregar_followup(request, patient_id):
    # Placeholder: Redirige al dashboard por ahora
    return redirect('followup_dashboard')

def editar_followup(request, pk):
    # Placeholder: Redirige al dashboard por ahora
    return redirect('followup_dashboard')

def eliminar_followup(request, pk):
    # Placeholder: Redirige al dashboard por ahora
    return redirect('followup_dashboard')

def ver_datos_siisa(request):
    # Placeholder
    return redirect('followup_dashboard')