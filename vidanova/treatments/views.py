from django.shortcuts import render
from rest_framework import viewsets
from .models import Treatment
from .serializers import TreatmentSerializer

class TreatmentViewSet(viewsets.ModelViewSet):
    queryset = Treatment.objects.all()
    serializer_class = TreatmentSerializer

