#!/usr/bin/env python
"""Script para eliminar la gráfica de Distribución por Género de followups.html"""

filepath = r"c:\Users\TICS 1\Desktop\ProyectoVidanova2\vidanova\followups\templates\followups.html"

with open(filepath, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar las líneas a eliminar (de la gráfica de género)
output_lines = []
skip_mode = False
skip_count = 0

for i, line in enumerate(lines):
    # Detectar inicio de sección de género
    if '<!-- Gráfico de Distribución por Género -->' in line:
        skip_mode = True
        skip_count = 0
        continue
    
    # En modo skip, contar líneas hasta encontrar el cierre del div de género
    if skip_mode:
        skip_count += 1
        if skip_count > 8:  # Aproximadamente 8 líneas para cerrar la tarjeta
            skip_mode = False
        elif '</div>' in line and skip_count > 5:
            skip_mode = False
            continue
        continue
    
    output_lines.append(line)

# Escribir el archivo actualizado
with open(filepath, 'w', encoding='utf-8') as f:
    f.writelines(output_lines)

print("✅ Sección HTML de género eliminada")

# Ahora eliminar las líneas del script JavaScript
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# Eliminar la sección de variables de género del script
content = content.replace(
    "    // Datos de género\n    const generoLabels = JSON.parse('{{ genero_labels|default:\"[]\"" +
    "|escapejs }}');\n    const generoValues = JSON.parse('{{ genero_values|default:\"[]\"" +
    "|escapejs }}');\n\n",
    ""
)

# Eliminar todo el bloque del gráfico de género (más tolerante)
start_marker = "// ---- Gráfica de Distribución por Género (Dona) ----"
if start_marker in content:
    start_idx = content.find(start_marker)
    # Encontrar el próximo bloque (// ----)
    next_marker_idx = content.find("// ----", start_idx + 10)
    if next_marker_idx != -1:
        content = content[:start_idx] + content[next_marker_idx:]
        print("✅ Sección JavaScript de género eliminada")

with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Proceso completado exitosamente")
