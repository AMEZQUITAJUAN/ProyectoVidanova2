# vidanova/followups/models.py
from django.db import models
from patients.models import Patient
from datetime import date

class FollowUp(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='seguimientos')

    # 🔹 Información clínica y administrativa
    fecha_atencion = models.DateField(null=True, blank=True)
    entidad_aseguradora = models.CharField(max_length=255, null=True, blank=True)
    cups = models.CharField(max_length=100, null=True, blank=True)
    servicio = models.CharField(max_length=255, null=True, blank=True)
    tipo = models.CharField(max_length=255, null=True, blank=True)
    grupo = models.CharField(max_length=255, null=True, blank=True)
    cantidad = models.IntegerField(null=True, blank=True)
    observaciones = models.TextField(null=True, blank=True)
    prioridad_atencion = models.CharField(max_length=100, null=True, blank=True)
    ubicacion = models.CharField(max_length=255, null=True, blank=True)
    profesional = models.CharField(max_length=255, null=True, blank=True)
    especialidad = models.CharField(max_length=255, null=True, blank=True)

    # 🔹 Diagnóstico
    codigo_grupo_diagnostico = models.CharField(max_length=100, null=True, blank=True)
    grupo_diagnostico = models.CharField(max_length=255, null=True, blank=True)
    codigo_diagnostico = models.CharField(max_length=100, null=True, blank=True)
    diagnostico = models.CharField(max_length=255, null=True, blank=True)
    ubicacion_diagnostico = models.CharField(max_length=255, null=True, blank=True)
    tipo_estadificacion_dx = models.CharField(max_length=255, null=True, blank=True)
    estadificacion_diagnostico = models.CharField(max_length=255, null=True, blank=True)

    # 🔹 Tiempos y estado
    tipo_paciente = models.CharField(max_length=255, null=True, blank=True)
    fecha_captacion = models.DateField(null=True, blank=True)
    tipo_procedimiento = models.CharField(max_length=255, null=True, blank=True)
    estado_solicitud = models.CharField(max_length=255, null=True, blank=True)
    fecha_solicitud_cita = models.DateField(null=True, blank=True)
    fecha_cita = models.DateField(null=True, blank=True)
    prestador = models.CharField(max_length=255, null=True, blank=True)
    barrera = models.CharField(max_length=255, null=True, blank=True)
    oportunidad = models.CharField(max_length=255, null=True, blank=True)
    ruta = models.CharField(max_length=255, null=True, blank=True)
    mes_ordenamiento = models.CharField(max_length=50, null=True, blank=True)
    semana_ordenamiento = models.CharField(max_length=50, null=True, blank=True)

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient} - {self.diagnostico or 'Sin diagnóstico'} ({self.fecha_atencion})"

    # --- CÁLCULO AUTOMÁTICO DE OPORTUNIDAD ---
    @property
    def dias_diff(self):
        """
        Calcula la diferencia en días entre la solicitud y la cita.
        """
        if self.fecha_cita and self.fecha_solicitud_cita:
            delta = self.fecha_cita - self.fecha_solicitud_cita
            return delta.days
        return None
    
    @property
    def dias_espera_actuales(self):
        """Calcula cuántos días han pasado desde la solicitud hasta HOY (si sigue pendiente)"""
        if self.fecha_solicitud_cita and not self.fecha_cita:
            return (date.today() - self.fecha_solicitud_cita).days
        return 0

    @property
    def es_alerta_roja(self):
        """Devuelve True si está PENDIENTE y lleva más de 30 días"""
        # Ajusta la lista de estados pendientes según tus reglas exactas
        estados_pendientes = ['PENDIENTE', 'EN_GESTION', 'POR_GESTIONAR', 'NO_AUTORIZADO']
        
        # Comparamos asegurándonos que el estado no sea None
        estado_actual = str(self.estado_solicitud).upper() if self.estado_solicitud else ''
        
        if estado_actual in estados_pendientes:
            if self.dias_espera_actuales > 30:
                return True
        return False