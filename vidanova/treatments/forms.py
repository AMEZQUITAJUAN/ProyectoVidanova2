from django import forms
from .models import Cycle

class CycleForm(forms.ModelForm):
    class Meta:
        model = Cycle
        fields = ['estado', 'fecha_real', 'notas']
        widgets = {
            'estado': forms.Select(attrs={'class': 'form-select'}),
            'fecha_real': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notas': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Efectos secundarios, observaciones...'}),
        }
        labels = {
            'fecha_real': 'Fecha Real de Aplicación',
        }