from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # Login y Logout
    path('', auth_views.LoginView.as_view(
        template_name='login.html', 
        redirect_authenticated_user=True
    ), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # Apps
    path('pacientes/', include('patients.urls')),
    path('seguimiento/', include('followups.urls')),
    
    # APIs
    path('api/tratamientos/', include('treatments.urls')),
    path('api/autorizaciones/', include('authorizations.urls')),
]

# --- FUERZA BRUTA PARA SERVIR ESTILOS EN WINDOWS/RED ---
# Esto asegura que login.css y sidebar.css carguen siempre
if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)