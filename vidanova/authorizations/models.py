# authorizations/models.py
from django.db import models
from patients.models import Patient

class Authorizations(models.Model):
    paciente = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='autorizaciones')
    numero = models.CharField(max_length=120, null=True, blank=True)
    tipo_servicio = models.CharField(max_length=120)  # Cirugía, Consulta, Imagen, Laboratorio, QMT...
    fecha_solicitud = models.DateField(null=True, blank=True)
    fecha_aprobacion = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=30, default='en_tramite')  # en_tramite, aprobada, negada
    observaciones = models.TextField(blank=True)

    def __str__(self): return f"{self.paciente} - {self.tipo_servicio} ({self.estado})"

