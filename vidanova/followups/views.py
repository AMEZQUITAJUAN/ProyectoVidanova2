from django.shortcuts import render
from django.db.models import Count, Avg, Q
from datetime import date
from .models import FollowUp
from patients.models import Patient
from treatments.models import Treatment
from authorizations.models import Authorizations as Authorization
from alerts.models import Alert
from appointments.models import Appointment


def followups(request):
    registros = FollowUp.objects.select_related('patient', 'treatment')

    # --- Estadísticas principales (KPIs) ---
    total = registros.count()
    completados = registros.filter(completed=True).count()
    pendientes = registros.filter(completed=False).count()
    porcentaje_completado = round((completados / total) * 100, 1) if total else 0
    porcentaje_pendiente = 100 - porcentaje_completado if total else 0

    # --- Promedio de días entre sesiones ---
    fechas = registros.values_list('session_date', flat=True).order_by('session_date')
    if len(fechas) > 1:
        diferencias = [(fechas[i] - fechas[i - 1]).days for i in range(1, len(fechas))]
        promedio_dias = round(sum(diferencias) / len(diferencias), 1)
    else:
        promedio_dias = 0

    # --- Datos por estado ---
    estado_data = {
        "pendiente": pendientes,
        "completado": completados,
        "agendado": Appointment.objects.count(),
        "por_gestionar": Authorization.objects.filter(Q(fecha_aprobacion__isnull=True)).count() if hasattr(Authorization, 'fecha_aprobacion') else 0
    }

    # --- Datos por tipo de tratamiento (para gráficos) ---
    procedimiento_data = (
        registros.values('treatment__tipo')
        .annotate(total=Count('id'))
        .order_by('treatment__tipo')
    )

    # --- Datos complementarios ---
    total_pacientes = Patient.objects.count()
    total_tratamientos = Treatment.objects.count()
    total_autorizaciones = Authorization.objects.count() if Authorization.objects.exists() else 0
    total_alertas = Alert.objects.count() if Alert.objects.exists() else 0

    # --- Alertas clasificadas (ejemplo básico) ---
    alertas = {
        "criticas": Alert.objects.filter(tipo="crítica").count() if hasattr(Alert, 'tipo') else 0,
        "advertencias": Alert.objects.filter(tipo="advertencia").count() if hasattr(Alert, 'tipo') else 0,
        "entiempo": Alert.objects.exclude(tipo__in=["crítica", "advertencia"]).count() if hasattr(Alert, 'tipo') else 0,
        "total": total_alertas
    }

    context = {
        "registros": registros,
        "stats": {
            "total": total,
            "completados": completados,
            "pendientes": pendientes,
            "porcentaje_completado": porcentaje_completado,
            "porcentaje_pendiente": porcentaje_pendiente,
            "promedio_dias": promedio_dias,
        },
        "estado_data": estado_data,
        "procedimiento_data": list(procedimiento_data),
        "alertas": alertas,
        "totales": {
            "pacientes": total_pacientes,
            "tratamientos": total_tratamientos,
            "autorizaciones": total_autorizaciones,
            "alertas": total_alertas,
        }
    }

    return render(request, 'followups.html', context)
