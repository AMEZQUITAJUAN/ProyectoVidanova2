from django.contrib import admin
from django.urls import path, include
from . import views as view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', view.login, name='login'),
    path('api/', include('patients.urls')), # /api/pacientes
    path('api/tratamientos/', include('treatments.urls')),
    path('api/autorizaciones/', include('authorizations.urls')),
    path('seguiniento/', include('followups.urls')),

]
