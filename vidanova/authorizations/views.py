from django.shortcuts import render
from rest_framework import viewsets
from .models import Authorizations
from .serializers import AuthorizationsSerializer

class AuthorizationsViewSet(viewsets.ModelViewSet):
    queryset = Authorizations.objects.all()
    serializer_class = AuthorizationsSerializer
