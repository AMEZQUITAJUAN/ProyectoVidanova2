from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views as view

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', view.login, name='login'),
    path('api/', include('patients.urls')), # /api/pacientes
    path('api/tratamientos/', include('treatments.urls')),
    path('api/autorizaciones/', include('authorizations.urls')),
    path('seguimiento/', include('followups.urls')),

]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
