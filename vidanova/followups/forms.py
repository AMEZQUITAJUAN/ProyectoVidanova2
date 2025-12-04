from django import forms
from .models import FollowUp

# --- 1. Formulario para Carga Masiva (Excel) ---
class UploadFileForm(forms.Form):
    archivo = forms.FileField(
        label="Selecciona el archivo Excel o CSV",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv, .xlsx, .xls'})
    )

# --- 2. Formulario para Edición Manual (CRUD) ---
class FollowUpForm(forms.ModelForm):
    # Campo "Fantasma": No existe en la BD, sirve para capturar la nota nueva
    nueva_observacion = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control', 
            'rows': 2, 
            'placeholder': 'Escribe aquí la nueva gestión o novedad...'
        }),
        required=False,
        label="Agregar Nueva Nota"
    )

    class Meta:
        model = FollowUp
        fields = [
            'patient', 'entidad_aseguradora', 'tipo_procedimiento', 'cups', 'servicio',
            'estado_solicitud', 'barrera',
            'fecha_solicitud_cita', 'fecha_cita', 
            'observaciones' # Este será el historial
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-select'}),
            'tipo_procedimiento': forms.Select(attrs={'class': 'form-select'}),
            'estado_solicitud': forms.Select(attrs={'class': 'form-select'}),
            'barrera': forms.Select(attrs={'class': 'form-select'}),
            'fecha_solicitud_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'cups': forms.TextInput(attrs={'class': 'form-control'}),
            
            # El historial lo mostramos gris y de solo lectura
            'observaciones': forms.Textarea(attrs={
                'class': 'form-control bg-light', 
                'rows': 4, 
                'readonly': 'readonly',
                'style': 'font-size: 0.9em; color: #555;'
            }),

            # Autocompletado
            'servicio': forms.TextInput(attrs={'class': 'form-control', 'list': 'servicios_list', 'placeholder': 'Escribe o selecciona...'}),
            'entidad_aseguradora': forms.TextInput(attrs={'class': 'form-control', 'list': 'aseguradoras_list', 'placeholder': 'Ej: SURA, SANITAS...'}),
        }
        labels = {
            'patient': 'Paciente',
            'entidad_aseguradora': 'Aseguradora (EPS)',
            'fecha_solicitud_cita': 'Fecha de Solicitud',
            'fecha_cita': 'Fecha de Cita',
            'barrera': 'Barrera Identificada',
            'observaciones': 'Historial de Bitácora (Lectura)'
        }