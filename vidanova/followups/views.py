from django.shortcuts import render, get_object_or_404, redirect
from django.db.models import Count, Max
from datetime import date
from .models import FollowUp
from patients.models import Patient
from treatments.models import Treatment
import json

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

