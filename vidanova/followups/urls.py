# followups/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.followups, name='followups'),  # <--- SOLO comillas vacías 'z
]
