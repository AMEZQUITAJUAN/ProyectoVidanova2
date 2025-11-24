from django import forms
from .models import FollowUp

# --- 1. Formulario para Carga Masiva (Excel) ---
class UploadFileForm(forms.Form):
    archivo = forms.FileField(
        label="Selecciona el archivo Excel o CSV",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv, .xlsx, .xls'})
    )

# --- 2. Formulario para Edición Manual (CRUD) ---
# followups/forms.py

class FollowUpForm(forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = [
            'patient', 'entidad_aseguradora', 'tipo_procedimiento', 'cups', 'servicio',
            'estado_solicitud', 'barrera',
            'fecha_solicitud_cita', 'fecha_cita', 
            'observaciones'
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-select'}),
            'tipo_procedimiento': forms.Select(attrs={'class': 'form-select'}),
            'estado_solicitud': forms.Select(attrs={'class': 'form-select'}),
            'barrera': forms.Select(attrs={'class': 'form-select'}),
            'fecha_solicitud_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'cups': forms.TextInput(attrs={'class': 'form-control'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),

            # --- AQUÍ ESTÁ EL TRUCO DEL AUTOCOMPLETADO ---
            # El atributo 'list' conecta el input con el <datalist> del HTML
            'servicio': forms.TextInput(attrs={'class': 'form-control', 'list': 'servicios_list', 'placeholder': 'Escribe o selecciona...'}),
            'entidad_aseguradora': forms.TextInput(attrs={'class': 'form-control', 'list': 'aseguradoras_list', 'placeholder': 'Ej: SURA, SANITAS...'}),
        }
        labels = {
            'patient': 'Paciente',
            'entidad_aseguradora': 'Aseguradora (EPS)',
            'fecha_solicitud_cita': 'Fecha de Solicitud',
            'fecha_cita': 'Fecha de Cita',
            'barrera': 'Barrera Identificada',
        }