from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import timedelta
from .models import Treatment, Cycle

@receiver(post_save, sender=Treatment)
def crear_ciclos_automaticos(sender, instance, created, **kwargs):
    """
    Cuando se crea un Tratamiento nuevo, genera los ciclos automáticamente
    proyectando las fechas futuras.
    """
    if created:
        ciclos_a_crear = []
        fecha_base = instance.fecha_inicio
        dias_salto = instance.frecuencia_dias

        for i in range(1, instance.total_ciclos + 1):
            # Ciclo 1 es la fecha inicio. Ciclo 2 es fecha_inicio + 21 días, etc.
            delta = timedelta(days=(i-1) * dias_salto)
            fecha_teorica = fecha_base + delta
            
            ciclo = Cycle(
                treatment=instance,
                numero=i,
                fecha_programada=fecha_teorica,
                estado='PROGRAMADO' if i > 1 else 'AGENDADO' # El primero asumimos que ya inicia
            )
            ciclos_a_crear.append(ciclo)
        
        Cycle.objects.bulk_create(ciclos_a_crear)