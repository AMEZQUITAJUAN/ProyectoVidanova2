# vidanova/followups/models.py
from django.db import models
from patients.models import Patient
from datetime import date
from django.contrib.auth.models import User

# --- EN FOLLOWUPS/MODELS.PY ---

class MasterCUP(models.Model):
    codigo = models.CharField(max_length=20, unique=True, db_index=True)
    descripcion = models.CharField(max_length=255, null=True, blank=True)
    
    # Las categorías oficiales que definimos
    CATEGORIAS = [
        ('PENDIENTE', '⚠️ PENDIENTE CLASIFICAR'),
        ('CONSULTA', 'CONSULTA ESPECIALIZADA'),
        ('QUIMIOTERAPIA', 'QUIMIOTERAPIA'),
        ('RADIOTERAPIA', 'RADIOTERAPIA'),
        ('CIRUGIA', 'CIRUGÍA'),
        ('IMAGEN', 'IMAGENOLOGÍA'),
        ('LABORATORIO', 'LABORATORIO CLÍNICO'),
        ('DOLOR', 'CLÍNICA DEL DOLOR'),
        ('ESTANCIA', 'ESTANCIA / HOSPITALIZACIÓN'),
        ('DIAGNOSTICO', 'PROCEDIMIENTO DIAGNÓSTICO'),
        ('COMPLEMENTARIO', 'SERVICIO COMPLEMENTARIO'),
        ('ONCOLOGIA', 'ONCOLOGÍA GENERAL'),
        ('OTROS', 'OTROS SERVICIOS'),
    ]
    
    grupo = models.CharField(max_length=50, choices=CATEGORIAS, default='PENDIENTE')
    
    def __str__(self):
        return f"{self.codigo} - {self.grupo}"

class FollowUp(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='seguimientos')

    # Datos Clínicos
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

    # Diagnóstico
    codigo_grupo_diagnostico = models.CharField(max_length=100, null=True, blank=True)
    grupo_diagnostico = models.CharField(max_length=255, null=True, blank=True)
    codigo_diagnostico = models.CharField(max_length=100, null=True, blank=True)
    diagnostico = models.CharField(max_length=255, null=True, blank=True)
    ubicacion_diagnostico = models.CharField(max_length=255, null=True, blank=True)
    tipo_estadificacion_dx = models.CharField(max_length=255, null=True, blank=True)
    estadificacion_diagnostico = models.CharField(max_length=255, null=True, blank=True)

    # Tiempos y estado
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
    agrupador = models.CharField(max_length=255, null=True, blank=True, db_index=True)
    
    # CAMPOS DE AUDITORÍA
    usuario_actualizacion = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True) # Se actualiza solo cada vez que guardas

    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient} - {self.tipo_procedimiento}"

    # --- LÓGICA DE NEGOCIO ---

    @property
    def dias_diff(self):
        """Calcula días entre solicitud y cita (puede dar negativo si hay error)."""
        if self.fecha_cita and self.fecha_solicitud_cita:
            delta = (self.fecha_cita - self.fecha_solicitud_cita).days
            return delta
        return None
    
    @property
    def es_inconsistente(self):
        """Detecta si la fecha de cita es ilógica (antes de la solicitud)."""
        d = self.dias_diff
        return d is not None and d < 0

    @property
    def dias_espera_actuales(self):
        """Días esperando hasta hoy."""
        if self.fecha_solicitud_cita and not self.fecha_cita:
            return (date.today() - self.fecha_solicitud_cita).days
        return 0

    @property
    def es_alerta_roja(self):
        """Alertar si está pendiente por más de 30 días."""
        estados_pendientes = ['PENDIENTE', 'EN_GESTION', 'POR_GESTIONAR', 'NO_AUTORIZADO']
        estado_actual = str(self.estado_solicitud).upper() if self.estado_solicitud else ''
        
        if any(e in estado_actual for e in estados_pendientes):
            if self.dias_espera_actuales > 30:
                return True
        return False