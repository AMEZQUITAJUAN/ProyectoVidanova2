# treatments/models.py
from django.db import models
from patients.models import Patient

class Treatment(models.Model):
    TTYPE = [('QMT','Quimioterapia'),('RX','Radioterapia'),('CIR','Cirugía'),('OTRO','Otro')]
    paciente = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='tratamientos')
    tipo = models.CharField(max_length=20, choices=TTYPE)
    fecha_inicio = models.DateField(null=True, blank=True)
    fecha_fin = models.DateField(null=True, blank=True)
    estado = models.CharField(max_length=20, choices=[('activo','Activo'),('suspendido','Suspendido'),('finalizado','Finalizado')], default='activo')
    causa_interrupcion = models.TextField(blank=True)
    observaciones = models.TextField(blank=True)

