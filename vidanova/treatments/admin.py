from django.contrib import admin
from .models import Treatment, Cycle

# Esto permite ver los ciclos DENTRO de la pantalla del tratamiento
class CycleInline(admin.TabularInline):
    model = Cycle
    extra = 0 # No mostrar filas vacías extra
    readonly_fields = ('fecha_programada',) # Para que veas que se calcularon solas
    can_delete = False

@admin.register(Treatment)
class TreatmentAdmin(admin.ModelAdmin):
    list_display = ('patient', 'nombre_esquema', 'fecha_inicio', 'progreso')
    list_filter = ('tipo',)
    search_fields = ('patient__numero_documento', 'nombre_esquema')
    inlines = [CycleInline] # Aquí conectamos los ciclos