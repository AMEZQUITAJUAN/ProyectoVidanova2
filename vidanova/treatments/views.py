from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Count, Q  # <--- Necesario para el reporte
from .models import Cycle, Treatment   # <--- AQUÍ ESTABA EL ERROR (Faltaba importar Treatment)
from .forms import CycleForm

# --- VISTA DE EDICIÓN DE CICLO (Ya existía) ---
@login_required
def editar_ciclo(request, pk):
    ciclo = get_object_or_404(Cycle, pk=pk)
    
    if request.method == 'POST':
        form = CycleForm(request.POST, instance=ciclo)
        if form.is_valid():
            form.save()
            
            patient_name = ciclo.treatment.patient.nombre_1
            messages.success(request, f"✅ Ciclo #{ciclo.numero} de {patient_name} actualizado.")
            
            return redirect('patient_profile', pk=ciclo.treatment.patient.id)
    
    return redirect('patient_profile', pk=ciclo.treatment.patient.id)

# --- VISTA DEL REPORTE CLÍNICO (La nueva) ---
@login_required
def reporte_tratamientos_activos(request):
    """
    Vista de Inteligencia Clínica: Muestra pacientes en curso y estadísticas.
    """
    # 1. Base: Solo tratamientos activos
    queryset = Treatment.objects.filter(activo=True).select_related('patient').prefetch_related('ciclos')
    
    # 2. Contadores (KPIs Clínicos)
    total_activos = queryset.count()
    
    # Conteo por tipo usando aggregate
    stats = queryset.aggregate(
        quimio=Count('id', filter=Q(tipo='QUIMIO')),
        radio=Count('id', filter=Q(tipo='RADIO')),
        inmuno=Count('id', filter=Q(tipo='INMUNO')),
        otros=Count('id', filter=Q(tipo__in=['ORAL', 'OTRO']))
    )

    # 3. Detectar pacientes por finalizar (Progreso > 80%)
    por_finalizar = []
    for t in queryset:
        if t.progreso >= 80:
            por_finalizar.append(t)

    context = {
        'tratamientos': queryset,
        'stats': stats,
        'total_activos': total_activos,
        'por_finalizar': por_finalizar,
        'count_finalizar': len(por_finalizar)
    }
    return render(request, 'treatments_report.html', context)