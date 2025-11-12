#!/usr/bin/env python
import re

# Ruta del archivo
filepath = r"c:\Users\TICS 1\Desktop\ProyectoVidanova2\vidanova\followups\templates\followups.html"

# Leer el contenido
with open(filepath, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Eliminar la sección HTML del gráfico de género
html_pattern = r'\s*<!-- Gráfico de Distribución por Género -->\s*<div class="card">\s*<h3><i class="fas fa-venus-mars"></i> Distribución por Género</h3>\s*<div style="height: 300px; margin-top: 16px; position: relative;">\s*<canvas id="chartGenero"></canvas>\s*</div>\s*</div>\s*'

content = re.sub(html_pattern, '\n', content)

# 2. Eliminar las líneas de variables generoLabels y generoValues del script
genero_vars_pattern = r'\s*// Datos de género\s*const generoLabels = JSON\.parse\(\'{{ genero_labels\|default:".*?escapejs }}\'\);\s*const generoValues = JSON\.parse\(\'{{ genero_values\|default:".*?escapejs }}\'\);\s*'

content = re.sub(genero_vars_pattern, '\n', content)

# 3. Eliminar el código de inicialización del gráfico de género
genero_chart_pattern = r'\s*// ---- Gráfica de Distribución por Género \(Dona\) ----\s*const generoCtx = document\.getElementById\(\'chartGenero\'\)\?\.getContext\(\'2d\'\);\s*if \(generoCtx\) \{\s*new Chart\(generoCtx, \{\s*type: \'doughnut\',\s*data: \{\s*labels: generoLabels,\s*datasets: \[\{\s*data: generoValues,\s*backgroundColor: colors\.slice\(0, generoLabels\.length\),\s*borderWidth: 1\s*\}\]\s*\},\s*options: \{\s*responsive: true,\s*maintainAspectRatio: false,\s*plugins: \{\s*legend: \{\s*position: \'bottom\',\s*labels: \{\s*usePointStyle: true,\s*padding: 20\s*\}\s*\}\s*\}\s*\}\s*\}\s*\);\s*\}\s*'

content = re.sub(genero_chart_pattern, '\n', content, flags=re.DOTALL)

# Escribir el contenido actualizado
with open(filepath, 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Gráfica de Distribución por Género eliminada exitosamente")
