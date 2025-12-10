from django.contrib import admin
from .models import FollowUp, MasterCUP

@admin.register(MasterCUP)
class MasterCUPAdmin(admin.ModelAdmin):
    list_display = ('codigo', 'grupo', 'descripcion')
    list_filter = ('grupo',) # ¡Filtra por PENDIENTE para ver qué falta!
    search_fields = ('codigo', 'descripcion')
    list_editable = ('grupo',) # Para editar rápido sin entrar al detalle
    ordering = ('grupo', 'codigo')

@admin.register(FollowUp)
class FollowUpAdmin(admin.ModelAdmin):
    list_display = ('patient', 'fecha_solicitud_cita', 'estado_solicitud')
    search_fields = ('patient__numero_documento',)
