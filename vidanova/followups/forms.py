from django import forms
from .models import FollowUp

class UploadFileForm(forms.Form):
    archivo = forms.FileField(
        label="Selecciona el archivo Excel o CSV",
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv, .xlsx, .xls'})
    )

class FollowUpForm(forms.ModelForm):
    class Meta:
        model = FollowUp
        fields = [
            'patient', 'tipo_procedimiento', 'cups', 'servicio',
            'estado_solicitud', 'barrera',
            'fecha_solicitud_cita', 'fecha_cita', 
            'observaciones'
        ]
        widgets = {
            'patient': forms.Select(attrs={'class': 'form-select select2'}), # Select2 ayuda con listas largas
            'tipo_procedimiento': forms.Select(attrs={'class': 'form-select'}),
            'estado_solicitud': forms.Select(attrs={'class': 'form-select'}),
            'barrera': forms.Select(attrs={'class': 'form-select'}),
            
            'fecha_solicitud_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'fecha_cita': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            
            'cups': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Código CUPS'}),
            'servicio': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Servicio o Especialidad'}),
            'observaciones': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }