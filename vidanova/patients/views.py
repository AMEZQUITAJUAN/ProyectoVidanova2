from django.shortcuts import render
from rest_framework import viewsets
from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Patient
from django.contrib.auth.decorators import login_required

@login_required
def patient_directory(request):
    """
    Lista todos los pacientes registrados con buscador y paginación.
    """
    # 1. Queryset Base (Ordenados por nombre)
    queryset = Patient.objects.all().order_by('nombre_1', 'apellido_1')
    
    # 2. Buscador Global
    q_search = request.GET.get('q')
    if q_search:
        queryset = queryset.filter(
            Q(numero_documento__icontains=q_search) |
            Q(nombre_1__icontains=q_search) |
            Q(nombre_2__icontains=q_search) |
            Q(apellido_1__icontains=q_search) |
            Q(apellido_2__icontains=q_search)
        )

    # 3. Paginación
    paginator = Paginator(queryset, 20) # 20 pacientes por página
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'patient_directory.html', {
        'page_obj': page_obj,
        'q_search': q_search
    })

def patient_profile(request, pk):
    """
    Perfil 360 del Paciente: Datos + Historial de Seguimientos.
    """
    patient = get_object_or_404(Patient, pk=pk)
    
    # Traemos el historial usando el related_name='seguimientos'
    # Asegúrate de que en followups/models.py el ForeignKey tenga related_name='seguimientos'
    history = patient.seguimientos.all().order_by('-fecha_solicitud_cita')

    return render(request, 'patient_profile.html', {
        'patient': patient,
        'history': history
    })