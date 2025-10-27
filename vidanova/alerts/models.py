from django.db import models
from patients.models import Patient

class Alert(models.Model):
    paciente = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='alertas')
    tipo_alerta = models.CharField(max_length=100)  # cita_vencida, sin_autorizacion, demora_tratamiento
    fecha_generada = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, default='activa')  # activa, resuelta
    observaciones = models.TextField(blank=True)
