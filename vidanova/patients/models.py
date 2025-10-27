# patients/models.py
from django.db import models

class Patient(models.Model):
    TIPS = [('CC','Cédula'), ('TI','Tarjeta'), ('CE','C.E.')]
    STATUS = [('active','Activo'),('fallecido','Fallecido'),('no_acepta','No acepta')]

    nombre = models.CharField(max_length=200)
    tipo_documento = models.CharField(max_length=10, choices=TIPS)
    numero_documento = models.CharField(max_length=50, db_index=True)
    fecha_nacimiento = models.DateField(null=True, blank=True)
    sexo = models.CharField(max_length=2, null=True, blank=True)
    eps = models.CharField(max_length=150, null=True, blank=True)
    tipo_cancer = models.CharField(max_length=200, null=True, blank=True)
    fecha_registro = models.DateTimeField(auto_now_add=True)
    estado = models.CharField(max_length=20, choices=STATUS, default='active')

    class Meta:
        unique_together = ('tipo_documento','numero_documento')

    def __str__(self):
        return f"{self.nombre} ({self.numero_documento})"
