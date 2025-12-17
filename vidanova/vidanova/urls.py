from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from . import views as view
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('admin/', admin.site.urls),
    
    # RUTA DE LOGIN (Usando tu diseño)
    path('', auth_views.LoginView.as_view(
        template_name='login.html', 
        redirect_authenticated_user=True # Si ya está logueado, lo manda al dashboard
    ), name='login'),
    
    # RUTA DE LOGOUT
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),

    # APPS
    path('pacientes/', include('patients.urls')),
    path('seguimiento/', include('followups.urls')),
]

if settings.DEBUG:
    # Servir archivos estáticos (CSS, JS, IMGs del diseño)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATICFILES_DIRS[0])
    
    # Servir archivos multimedia (Excels subidos)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)