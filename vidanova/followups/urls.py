from django.urls import path
from . import views

urlpatterns = [
    # 1. Dashboard Principal
    path('', views.followup_dashboard, name='followup_dashboard'),
    path('inicio/', views.followup_dashboard, name='followups'), # Alias por compatibilidad

    # 2. Carga de Datos
    path('cargar-datos/', views.importar_datos, name='cargar_datos'),

    # 3. Análisis Institucional (El error actual)
    path('analisis-institucional/', views.analisis_institucional, name='analisis_institucional'),
    path('ver-datos/', views.ver_datos_siisa, name='ver_datos_siisa'),

    # 4. CRUD y Detalles (Necesarios para los botones de la tabla)
    # Nota: pk es la llave primaria (ID del seguimiento)
    path('detalle/<int:pk>/', views.followup_detail, name='followup_detail'),
    path('paciente/<int:patient_id>/agregar/', views.agregar_followup, name='agregar_followup'),
    path('editar/<int:pk>/', views.editar_followup, name='editar_followup'),
    path('eliminar/<int:pk>/', views.eliminar_followup, name='eliminar_followup'),
    path('exportar/', views.exportar_excel, name='exportar_excel'),
]