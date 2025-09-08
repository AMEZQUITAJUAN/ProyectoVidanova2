# seguimiento/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.seguimiento, name='seguimiento'),  # <--- SOLO comillas vacías 'z
]
