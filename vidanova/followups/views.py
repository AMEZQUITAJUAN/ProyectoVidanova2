from django.shortcuts import render, get_object_or_404
from django.db.models import Count, Avg, Q
from datetime import date
from .models import FollowUp
from followups.models import FollowUp
from patients.models import Patient
from treatments.models import Treatment
from authorizations.models import Authorizations as Authorization
from alerts.models import Alert
from appointments.models import Appointment
import json

def followup_detail(request, patient_id):
    # Obtiene el paciente o devuelve 404 si no existe
    paciente = get_object_or_404(Patient, id=patient_id)

    # Trae todos los seguimientos del paciente
    seguimientos = FollowUp.objects.filter(patient=paciente).select_related('treatment').order_by('-session_date')

    # Métricas simples
    total = seguimientos.count()
    completados = seguimientos.filter(completed=True).count()
    pendientes = total - completados

    context = {
        "paciente": paciente,
        "seguimientos": seguimientos,
        "stats": {
            "total": total,
            "completados": completados,
            "pendientes": pendientes
        }
    }

    return render(request, "followup_detail.html", context)

def followups(request):
    registros = FollowUp.objects.select_related('patient', 'treatment')

    # ---- Filtros dinámicos (usando tus nombres actuales) ----
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

    # ---- Métricas ----
    total = registros.count()
    completados = registros.filter(completed=True).count()
    pendientes = registros.filter(completed=False).count()
    porcentaje_completado = round((completados / total) * 100, 1) if total else 0
    porcentaje_pendiente = 100 - porcentaje_completado

    # ---- Datos para gráficas ----
    estado_data = {
        "pendiente": pendientes,
        "completado": completados,
        "agendado": 0,
        "por_gestionar": 0
    }

    procedimiento_data = (
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
            "promedio_dias": "-",
        },
        "estado_data": json.dumps(estado_data),
        "procedimiento_data": json.dumps(list(procedimiento_data)),
        "alertas": {
            "criticas": 2,
            "advertencias": 3,
            "entiempo": 4,
            "total": total
        },
        # 🔹 Enviamos los valores actuales de los filtros al HTML
        "filtros": {
            "date_from": date_from or "",
            "date_to": date_to or "",
            "status": status or "",
            "procedure": procedure or "",
        }
    }

    print("Estado data:", estado_data)
    print("Procedimiento data:", list(procedimiento_data))

    return render(request, 'followups.html', context)
