# appointments/models.py
from django.db import models
from patients.models import Patient

class Appointment(models.Model):
    paciente = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='citas')
    fecha_programada = models.DateTimeField()
    fecha_realizada = models.DateTimeField(null=True, blank=True)
    tipo = models.CharField(max_length=120)  # control, QMT, RX, cirugia
    prestador = models.CharField(max_length=200, blank=True)
    estado = models.CharField(max_length=30, default='agendada')  # agendada, cumplida, cancelada, pendiente
    observaciones = models.TextField(blank=True)

