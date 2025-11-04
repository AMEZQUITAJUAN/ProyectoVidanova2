from django.urls import path
from . import views

urlpatterns = [
    path('', views.followups, name='followups'),
    path('paciente/<int:patient_id>/', views.followup_detail, name='followup_detail'),
]

