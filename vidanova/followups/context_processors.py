# followups/context_processors.py
from django.utils import timezone
from datetime import timedelta
from django.db.models import F, Q
from .models import FollowUp

def alertas_globales(request):
    """
    Calcula alertas visibles en todo el sitio web (Navbar).
    """
    if not request.user.is_authenticated:
        return {}
    
    # 1. ALERTA DE INCONSISTENCIAS LÓGICAS
    # (Fecha Cita es ANTERIOR a Fecha Solicitud)
    inconsistencias = FollowUp.objects.filter(
        fecha_cita__lt=F('fecha_solicitud_cita')
    ).count()
    
    # 2. ALERTA DE VENCIMIENTO (> 30 Días sin respuesta)
    # Calculamos la fecha límite (Hoy - 30 días)
    fecha_limite = timezone.now().date() - timedelta(days=30)
    
    # Estados que consideramos "Abiertos"
    estados_pendientes = ['PENDIENTE', 'EN_GESTION', 'POR_GESTIONAR', 'NO_AUTORIZADO']
    
    vencidos = FollowUp.objects.filter(
        estado_solicitud__in=estados_pendientes,   # Está pendiente
        fecha_solicitud_cita__lt=fecha_limite,     # Fue hace más de 30 días
        fecha_cita__isnull=True                    # Y aún no tiene cita
    ).count()
    
    total_alertas = inconsistencias + vencidos
    
    return {
        'alert_total': total_alertas,
        'alert_inconsistent': inconsistencias,
        'alert_overdue': vencidos
    }