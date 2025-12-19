from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import Cycle
from .forms import CycleForm

@login_required
def editar_ciclo(request, pk):
    ciclo = get_object_or_404(Cycle, pk=pk)
    
    if request.method == 'POST':
        form = CycleForm(request.POST, instance=ciclo)
        if form.is_valid():
            form.save()
            
            # Mensaje de éxito
            patient_name = ciclo.treatment.patient.nombre_1
            messages.success(request, f"✅ Ciclo #{ciclo.numero} de {patient_name} actualizado.")
            
            # Redirigir al perfil del paciente
            return redirect('patient_profile', pk=ciclo.treatment.patient.id)
    
    # Si algo falla, volvemos al perfil
    return redirect('patient_profile', pk=ciclo.treatment.patient.id)