# followups/templatetags/followups_extras.py
from django import template
from django.contrib.auth.models import Group


register = template.Library()

@register.simple_tag(takes_context=True)
def param_replace(context, **kwargs):
    """
    Permite actualizar parámetros GET en la URL (como la página) 
    sin perder los filtros actuales (como la búsqueda o fechas).
    Uso: {% param_replace page=next_page %}
    """
    d = context['request'].GET.copy()
    for k, v in kwargs.items():
        d[k] = v
    for k in [k for k, v in d.items() if not v]:
        del d[k]
    return d.urlencode()

@register.filter(name='has_group')
def has_group(user, group_name):
    """
    Uso en HTML: {% if request.user|has_group:"Gestores" %}
    Devuelve True si el usuario pertenece al grupo.
    """
    if user.is_superuser:
        return True # El superadmin tiene todos los poderes
    return user.groups.filter(name=group_name).exists()