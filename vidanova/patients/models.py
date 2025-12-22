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
    
    # Demográficos Campos
    correo = models.EmailField(null=True, blank=True)
    genero = models.CharField(max_length=50, null=True, blank=True)
    edad = models.PositiveIntegerField(null=True, blank=True)
    ocupacion = models.CharField(max_length=150, null=True, blank=True)
    escolaridad = models.CharField(max_length=150, null=True, blank=True)
    departamento_residencia = models.CharField(max_length=150, null=True, blank=True)
    ciudad_residencia = models.CharField(max_length=150, null=True, blank=True)
    estado_natural = models.CharField(max_length=100, null=True, blank=True)
    telefono = models.CharField(max_length=50, null=True, blank=True, verbose_name="Teléfono / Celular")

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
    
    @property
    def link_whatsapp(self):
        """
        Genera el enlace directo para abrir WhatsApp.
        Limpia el número y agrega el indicativo de Colombia (57).
        """
        if not self.telefono:
            return None
        
        # 1. Dejar solo números (quitar espacios, guiones, letras)
        numero_limpio = "".join(filter(str.isdigit, str(self.telefono)))
        
        # 2. Validar longitud mínima (un celular tiene 10 dígitos)
        if len(numero_limpio) < 10:
            return None
            
        # 3. Agregar indicativo 57 si no lo tiene
        if not numero_limpio.startswith('57'):
            numero_limpio = '57' + numero_limpio
            
        # 4. Crear Mensaje Predeterminado
        mensaje = f"Hola {self.nombre_1.title()}, te saludamos de Vidanova IPS. Nos comunicamos respecto a tu solicitud."
        
        # Retornar URL
        return f"https://wa.me/{numero_limpio}?text={mensaje}"
    
    @property
    def numero_limpio(self):
        """Devuelve solo el número con indicativo (57300...) para usar en templates."""
        if not self.telefono: return None
        num = "".join(filter(str.isdigit, str(self.telefono)))
        if len(num) < 10: return None
        if not num.startswith('57'): num = '57' + num
        return num
    

    

    
    