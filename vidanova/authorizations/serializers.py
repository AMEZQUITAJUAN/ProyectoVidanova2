from rest_framework import serializers
from .models import Authorizations

class AuthorizationsSerializer(serializers.ModelSerializer):
    class Meta:
        model = Authorizations
        fields = '__all__'
