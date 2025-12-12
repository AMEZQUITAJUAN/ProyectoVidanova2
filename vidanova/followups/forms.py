from django import forms
from .models import FollowUp

# --- 1. Formulario para Carga Masiva ---
class UploadFileForm(forms.Form):
    archivo = forms.FileField(
        label="Selecciona el archivo Excel o CSV",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv, .xlsx, .xls'})
    )

# --- 2. Formulario para Edición Manual (CRUD) ---
class FollowUpForm(forms.ModelForm):
    # Campo "Fantasma" para la bitácora
    nueva_observacion = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 2, 
            'placeholder': 'Escribe aquí la nueva gestión...'
        }),
        required=False,
        label="Agregar Nueva Nota"
    )

    class Meta:
        model = FollowUp
        fields = [
            'patient', 'entidad_aseguradora', 'tipo_procedimiento', 'cups', 
            'estado_solicitud', 'barrera',
            'fecha_solicitud_cita', 'fecha_cita', 
            'observaciones',
            'prestador', 'tipo_paciente'
        ]
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # --- DEFINICIÓN DE LISTAS DESPLEGABLES ---

        # 1. ESTADOS (Semaforización)
        ESTADOS = [
            ('PENDIENTE', 'PENDIENTE'),
            ('EN_GESTION', 'EN GESTIÓN'),
            ('AGENDADO', 'AGENDADO'),
            ('REALIZADO', 'REALIZADO'),
            ('CANCELADO', 'CANCELADO'),
        ]
        self.fields['estado_solicitud'].widget = forms.Select(choices=ESTADOS, attrs={'class': 'form-select'})

        # 2. PROCEDIMIENTOS (Categorías Maestras)
        # Usamos las mismas categorías que en el filtro para mantener orden
        PROCEDIMIENTOS = [
            ('', '-- Seleccionar --'),
            ('CONSULTA', 'Consulta Especializada'),
            ('QUIMIOTERAPIA', 'Quimioterapia'),
            ('RADIOTERAPIA', 'Radioterapia'),
            ('CIRUGIA', 'Cirugía'),
            ('IMAGENOLOGIA', 'Imagenología'),
            ('LABORATORIO', 'Laboratorio Clínico'),
            ('DOLOR', 'Clínica del Dolor'),
            ('ESTANCIA', 'Estancia / Hospitalización'),
            ('PROCEDIMIENTO DIAGNOSTICO', 'Procedimiento Diagnóstico'),
            ('SERVICIO COMPLEMENTARIO', 'Servicio Complementario'),
            ('ONCOLOGIA', 'Oncología General'),
            ('OTROS', 'Otros'),
        ]
        # Nota: Si el dato original no coincide con esta lista, aparecerá seleccionado "-- Seleccionar --"
        # y la gestora deberá clasificarlo correctamente.
        self.fields['tipo_procedimiento'].widget = forms.Select(choices=PROCEDIMIENTOS, attrs={'class': 'form-select'})

        # 3. BARRERAS (Lista Estandarizada)
        BARRERAS = [
            ('', 'Ninguna / Sin Barrera'),
            ('No contesta', 'No contesta / Ilocalizable'),
            ('Sin convenio', 'Sin convenio con EPS'),
            ('Orden vencida', 'Orden vencida'),
            ('Falta autorización', 'Falta autorización de EPS'),
            ('Agenda cerrada', 'Agenda cerrada / Sin disponibilidad'),
            ('Paciente no acepta', 'Paciente no acepta cita/prestador'),
            ('Reprogramado', 'Reprogramado por paciente'),
            ('Domicilio lejano', 'Domicilio lejano / Transporte'),
            ('Fallecido', 'Paciente Fallecido'),
            ('Otro', 'Otro motivo (Ver observaciones)'),
        ]
        self.fields['barrera'].widget = forms.Select(choices=BARRERAS, attrs={'class': 'form-select'})

        # 4. PRESTADORES
        PRESTADORES = [
            ('', '-- Seleccionar --'),
            ('Vidanova', 'Vidanova'),
            ('Andes del sur', 'Andes del sur'),
            ('BIOS', 'BIOS'),
            ('Cardio Imagenes', 'Cardio Imágenes'),
            ('CIMO', 'CIMO'),
            ('Clinica Imbanaco', 'Clínica Imbanaco'),
            ('Clinica La Estancia', 'Clínica La Estancia'),
            ('Clinica San Rafael', 'Clínica San Rafael'),
            ('Clinica Santa Gracia', 'Clínica Santa Gracia'),
            ('Dumian', 'Dumian'),
            ('Fundacion Corazon y Pulmon', 'Fundación Corazón y Pulmón'),
            ('Gamanuclear', 'Gamanuclear'),
            ('Laboratorio Adriana Correa', 'Laboratorio Adriana Correa'),
            ('Previred', 'Previred'),
            ('Otros', 'Otros'),
        ]
        self.fields['prestador'].widget = forms.Select(choices=PRESTADORES, attrs={'class': 'form-select'})

        # 5. TIPO PACIENTE
        TIPOS = [('', '-- Seleccionar --'), ('INCIDENTE', 'INCIDENTE'), ('PREVALENTE', 'PREVALENTE')]
        self.fields['tipo_paciente'].widget = forms.Select(choices=TIPOS, attrs={'class': 'form-select'})

        # OTROS CAMPOS
        self.fields['fecha_solicitud_cita'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['fecha_cita'].widget = forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
        self.fields['observaciones'].widget.attrs.update({'readonly': 'readonly', 'class': 'form-control bg-light text-muted'})
        self.fields['cups'].widget.attrs.update({'class': 'form-control'})
        self.fields['entidad_aseguradora'].widget.attrs.update({'class': 'form-control'})