from django.urls import path
from . import views

urlpatterns = [
    path('editar-ciclo/<int:pk>/', views.editar_ciclo, name='editar_ciclo'),
    path('reporte-activos/', views.reporte_tratamientos_activos, name='reporte_tratamientos_activos'),
]