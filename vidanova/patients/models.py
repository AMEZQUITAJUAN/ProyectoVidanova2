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

    # 🔹 Identificación básica
    tipo_documento = models.CharField(max_length=5, choices=TIPOS_DOC)
    numero_documento = models.CharField(max_length=50, db_index=True, unique=True)

    # 🔹 Datos personales
    nombre_1 = models.CharField(max_length=100)
    nombre_2 = models.CharField(max_length=100, null=True, blank=True)
    apellido_1 = models.CharField(max_length=100)
    apellido_2 = models.CharField(max_length=100, null=True, blank=True)
    correo = models.EmailField(null=True, blank=True)
    genero = models.CharField(max_length=50, null=True, blank=True)
    edad = models.PositiveIntegerField(null=True, blank=True)
    ocupacion = models.CharField(max_length=150, null=True, blank=True)
    escolaridad = models.CharField(max_length=150, null=True, blank=True)
    departamento_residencia = models.CharField(max_length=150, null=True, blank=True)
    ciudad_residencia = models.CharField(max_length=150, null=True, blank=True)
    estado_natural = models.CharField(max_length=100, null=True, blank=True)

    # 🔹 Registro administrativo
    fecha_registro = models.DateTimeField(auto_now_add=True)
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre_1} {self.apellido_1} ({self.numero_documento})"
    # ... (resto de tus campos) ...
    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.nombre_1} {self.apellido_1} ({self.numero_documento})"
    
    # --- AGREGA ESTO AL FINAL DE LA CLASE ---
    @property
    def nombre(self):
        """Une los nombres para mostrar el nombre completo automáticamente"""
        n2 = f" {self.nombre_2}" if self.nombre_2 else ""
        a2 = f" {self.apellido_2}" if self.apellido_2 else ""
        return f"{self.nombre_1}{n2} {self.apellido_1}{a2}"

    @property
    def documento(self):
        """Alias para que el código que usa .documento funcione con .numero_documento"""
        return self.numero_documento

