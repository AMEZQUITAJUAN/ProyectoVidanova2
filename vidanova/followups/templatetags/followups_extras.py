# followups/templatetags/followups_extras.py
from django import template

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