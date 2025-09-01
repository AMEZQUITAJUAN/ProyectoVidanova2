from django.urls import path
from . import views

urlpatterns = [
    path('seguimiento/', views.seguimiento, name='seguimiento'),
]
