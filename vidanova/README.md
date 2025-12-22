# 🏥 Sistema de Gestión Oncológica Vidanova

Sistema integral para el seguimiento administrativo y clínico de pacientes oncológicos. Diseñado para centralizar la información dispersa en archivos Excel, automatizar el cálculo de fechas de tratamiento y proveer inteligencia de negocios en tiempo real.

---

## 🚀 Características Principales

### 1. Ingesta de Datos Blindada (ETL)
El sistema cuenta con un motor de importación inteligente (`services.py`) capaz de procesar archivos Excel/CSV heterogéneos.
- **Header Hunter V4:** Detecta automáticamente la fila de encabezados buscando patrones de palabras clave, ignorando filas vacías o logotipos.
- **Normalización:** Estandariza nombres de EPS ("Asmet" -> "ASMET SALUD") y corrige formatos de fecha automáticamente.
- **Lógica Upsert:** Detecta si un registro ya existe (Firma: Paciente + Fecha + Procedimiento) para actualizarlo en lugar de duplicarlo.

### 2. Gestión Operativa
- **Acciones Masivas:** Modal para cambiar estado, asignar prestador o escribir en bitácora para múltiples pacientes a la vez.
- **Bitácora (Audit Log):** Sistema de historial que registra quién escribió la nota y cuándo, sin sobrescribir la información anterior.
- **Macros:** Botones de texto rápido para agilizar la tipificación de notas de gestión.

### 3. Módulo Clínico (Tratamientos)
- **Proyección Automática:** Al crear un tratamiento (ej: Quimioterapia, 4 ciclos cada 21 días), un **Robot (Signal)** calcula y crea automáticamente las fechas futuras de todos los ciclos.
- **Control de Adherencia:** Compara Fecha Programada vs. Fecha Real.

### 4. Inteligencia de Negocios
- **Tablero Operativo:** Filtros dinámicos y persistentes (Memoria de sesión).
- **Análisis Gerencial:** Gráficas de Top Barreras, Top EPS y tendencias mensuales.
- **Auditoría de Calidad:** Módulo técnico para detectar duplicados y registros incompletos.
- **Alertas Proactivas:** Campana de notificaciones que detecta vencimientos (>30 días) e inconsistencias de fechas.

---

## 🛠️ Stack Tecnológico

*   **Backend:** Python 3, Django 5.
*   **Base de Datos:** SQLite (Portátil y robusta para este volumen).
*   **Procesamiento:** Pandas (ETL), OpenPyXL (Reportes).
*   **Frontend:** Bootstrap 5, Chart.js (Gráficas), FullCalendar (Agenda).
*   **Servidor:** Waitress (Producción en Windows) + WhiteNoise (Archivos Estáticos).

---

## 📂 Estructura del Proyecto

```text
vidanova/
├── followups/          # Módulo Administrativo (Citas, Autorizaciones)
│   ├── services.py     # LÓGICA CRÍTICA: Importador y Métricas.
│   ├── context_processors.py # Lógica de la Campana de Alertas.
│   └── views.py        # Controladores del Tablero y Auditoría.
│
├── patients/           # Módulo de Pacientes
│   ├── models.py       # Modelo del Paciente (Lógica de Nombre Completo).
│   └── views.py        # Directorio y Perfil 360.
│
├── treatments/         # Módulo Clínico
│   ├── models.py       # Tratamientos y Ciclos.
│   └── signals.py      # ROBOT: Generador automático de ciclos.
│
├── static/             # Archivos CSS, JS e Imágenes.
├── templates/          # HTML (Layout, Login, Dashboards).
├── manage.py           # Ejecutor de Django.
├── iniciar.bat         # Script de arranque para Windows.
└── silencioso.vbs      # Script para ejecución en segundo plano.

🔐 Roles y Permisos
El sistema se gestiona mediante Grupos de Django Admin:
Superusuario (Admin): Acceso total. Puede ver Auditoría, Borrar registros y Descargar Backups.
Gestores (Operativo): Pueden Cargar archivos, Editar pacientes y gestionar ciclos. NO pueden borrar ni auditar.
Gerencia: Solo lectura. Acceso a Tableros y Gráficas. Puede clasificar CUPS nuevos.

⚙️ Instalación y Despliegue


1. Requisitos Previos
Python 3.10 o superior.
Entorno virtual recomendado.

2. Instalación de Dependencias
code
Bash
pip install django pandas openpyxl waitress whitenoise xhtml2pdf

3. Configuración Inicial
code
Bash
python manage.py migrate
python manage.py collectstatic
python manage.py createsuperuser

4. Ejecución en Producción (Red Local)
El sistema está configurado para correr en red local (LAN).
Opción A: Manual
code
Bash
python manage.py runserver 0.0.0.0:8000
Opción B: Automática (Windows)
El sistema incluye un script iniciar.bat y silencioso.vbs.
Colocar un acceso directo de silencioso.vbs en la carpeta shell:startup de Windows para que el servidor inicie automáticamente al encender el PC.

🧪 Solución de Problemas Comunes
1. "No cargan los estilos en otros PCs"
Verificar que DEBUG = True en settings.py (si no se usa WhiteNoise estricto).
Asegurar que el bloque de mimetypes está en settings.py para corregir el bug de registro de Windows.

2. "El archivo Excel no carga"
Revisar la consola del servidor. El "Header Hunter" indicará qué columnas detectó.
Si es un formato nuevo, agregar las palabras clave al diccionario en followups/services.py.

3. "Database is locked"
Ocurre si se interrumpe una carga masiva. Reiniciar el servidor para liberar el archivo SQLite.

Desarrollado para Vidanova IPS
Última actualización: Diciembre 2025