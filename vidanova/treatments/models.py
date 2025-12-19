# treatments/models.py
from django.db import models
from patients.models import Patient
from datetime import timedelta

class Treatment(models.Model):
    """
    Representa el esquema general (ej: 'Quimioterapia de Primera Línea')
    """
    TIPOS = [
        ('QUIMIO', 'Quimioterapia'),
        ('RADIO', 'Radioterapia'),
        ('INMUNO', 'Inmunoterapia'),
        ('ORAL', 'Terapia Oral'),
        ('OTRO', 'Otro'),
    ]

    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name='tratamientos')
    tipo = models.CharField(max_length=20, choices=TIPOS, default='QUIMIO')
    nombre_esquema = models.CharField(max_length=150, help_text="Ej: Esquema AC-T (Doxorrubicina + Ciclofosfamida)")
    
    fecha_inicio = models.DateField(verbose_name="Fecha Inicio Ciclo 1")
    frecuencia_dias = models.PositiveIntegerField(default=21, help_text="Cada cuántos días es el ciclo (ej: 21)")
    total_ciclos = models.PositiveIntegerField(default=1, help_text="Cuántos ciclos se ordenaron")
    
    activo = models.BooleanField(default=True)
    observaciones = models.TextField(blank=True, null=True)
    
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.patient} - {self.nombre_esquema}"

    @property
    def progreso(self):
        """Calcula porcentaje de avance (Ciclos realizados / Total)"""
        realizados = self.ciclos.filter(estado='REALIZADO').count()
        if self.total_ciclos > 0:
            return round((realizados / self.total_ciclos) * 100)
        return 0

class Cycle(models.Model):
    """
    Cada una de las sesiones del tratamiento
    """
    ESTADOS = [
        ('PROGRAMADO', 'Programado (Teórico)'),
        ('AGENDADO', 'Cita Asignada'),
        ('REALIZADO', 'Administrado/Realizado'),
        ('CANCELADO', 'Cancelado/Perdido'),
    ]

    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE, related_name='ciclos')
    numero = models.PositiveIntegerField(verbose_name="# Ciclo")
    
    fecha_programada = models.DateField(help_text="Fecha teórica calculada")
    fecha_real = models.DateField(null=True, blank=True, help_text="Cuando realmente se hizo")
    
    estado = models.CharField(max_length=20, choices=ESTADOS, default='PROGRAMADO')
    notas = models.TextField(blank=True, null=True)

    class Meta:
        ordering = ['numero']

    def __str__(self):
        return f"Ciclo {self.numero} - {self.treatment}"

