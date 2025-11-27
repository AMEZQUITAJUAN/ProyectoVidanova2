# patients/models.py
from django.db import models

class Patient(models.Model):
    TIPOS_DOC = [
        ('CC', 'Cédula de Ciudadanía'),
        ('TI', 'Tarjeta de Identidad'),
        ('CE', 'Cédula de Extranjería'),
        ('PA', 'Pasaporte'),
        ('OT', 'Otro'),
    ]

    # Identificación
    tipo_documento = models.CharField(max_length=5, choices=TIPOS_DOC, default='CC')
    numero_documento = models.CharField(max_length=50, db_index=True, unique=True)

    # Datos Personales
    nombre_1 = models.CharField(max_length=100)
    nombre_2 = models.CharField(max_length=100, null=True, blank=True)
    apellido_1 = models.CharField(max_length=100)
    apellido_2 = models.CharField(max_length=100, null=True, blank=True)
    
    # Demográficos
    correo = models.EmailField(null=True, blank=True)
    genero = models.CharField(max_length=50, null=True, blank=True)
    edad = models.PositiveIntegerField(null=True, blank=True)
    ocupacion = models.CharField(max_length=150, null=True, blank=True)
    escolaridad = models.CharField(max_length=150, null=True, blank=True)
    departamento_residencia = models.CharField(max_length=150, null=True, blank=True)
    ciudad_residencia = models.CharField(max_length=150, null=True, blank=True)
    estado_natural = models.CharField(max_length=100, null=True, blank=True)

    # Auditoría
    fecha_registro = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre_completo} ({self.numero_documento})"
    
    @property
    def nombre_completo(self):
        """
        Concatena inteligentemente las 4 partes del nombre.
        Ej: "JUAN" + None + "PEREZ" + "GOMEZ" -> "JUAN PEREZ GOMEZ"
        """
        partes = [
            self.nombre_1, 
            self.nombre_2, 
            self.apellido_1, 
            self.apellido_2
        ]
        # Filtramos los None o vacíos, unimos con espacio y pasamos a mayúsculas
        nombre_limpio = " ".join([str(p).strip() for p in partes if p and str(p).strip()])
        return nombre_limpio.upper()

    @property
    def documento(self):
        return self.numero_documento