from django.urls import path
from . import views

urlpatterns = [
    # Ruta base: Directorio / Buscador
    path('', views.patient_directory, name='patient_directory'),
    
    # Ruta detalle: Perfil 360 del paciente
    path('perfil/<int:pk>/', views.patient_profile, name='patient_profile'),
    path('pdf/<int:pk>/', views.generar_pdf_paciente, name='generar_pdf_paciente'),
]