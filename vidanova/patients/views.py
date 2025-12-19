from django.shortcuts import render, get_object_or_404
from django.core.paginator import Paginator
from django.db.models import Q
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse  # <--- ESTA FUE LA LÍNEA QUE FALTÓ
from django.utils import timezone
from vidanova.utils import render_to_pdf
from .models import Patient

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

# --- EN PATIENTS/VIEWS.PY ---

@login_required
def patient_profile(request, pk):
    """
    Perfil 360: Datos + Historial Administrativo + Tratamientos Clínicos.
    """
    patient = get_object_or_404(Patient, pk=pk)
    
    # 1. Historial Administrativo (Lo que ya tenías)
    history = patient.seguimientos.all().order_by('-fecha_solicitud_cita')

    # 2. Tratamientos Clínicos (LO NUEVO)
    # Usamos 'prefetch_related' para traer los ciclos eficientemente y no hacer mil consultas
    treatments = patient.tratamientos.prefetch_related('ciclos').all().order_by('-fecha_inicio')

    return render(request, 'patient_profile.html', {
        'patient': patient,
        'history': history,
        'treatments': treatments # <--- Enviamos esto a la plantilla
    })

# --- GENERACIÓN DE PDF ---
@login_required
def generar_pdf_paciente(request, pk):
    """
    Genera un reporte PDF completo del historial del paciente.
    """
    patient = get_object_or_404(Patient, pk=pk)
    history = patient.seguimientos.all().order_by('-fecha_solicitud_cita')
    
    data = {
        'patient': patient,
        'history': history,
        'fecha_impresion': timezone.now(),
        'usuario': request.user.username.title(),
    }
    
    pdf = render_to_pdf('patient_pdf.html', data)
    
    if pdf:
        response = HttpResponse(pdf, content_type='application/pdf')
        filename = f"Historia_{patient.numero_documento}.pdf"
        response['Content-Disposition'] = f'inline; filename="{filename}"'
        return response
    
    return HttpResponse("Error generando PDF", status=404)