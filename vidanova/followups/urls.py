from django.urls import path
from . import views

urlpatterns = [
    path('', views.followups, name='followups'),
    path('paciente/<int:patient_id>/', views.followup_detail, name='followup_detail'),
    path('paciente/<int:patient_id>/agregar/', views.agregar_followup, name='agregar_followup'),
    path('editar/<int:pk>/', views.editar_followup, name='editar_followup'),
    path('eliminar/<int:pk>/', views.eliminar_followup, name='eliminar_followup'),
]
