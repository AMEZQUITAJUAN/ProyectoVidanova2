# 🏥 Sistema de Gestión Oncológica Vidanova

**Versión:** 1.0 (Producción Local)
**Estado:** Estable / En Uso

Sistema integral para el seguimiento administrativo y clínico de pacientes oncológicos. Diseñado para centralizar la información dispersa, automatizar la proyección de tratamientos, gestionar la comunicación con pacientes y proveer inteligencia de negocios.

---

## 🚀 Características Principales

### 1. Ingesta de Datos & Inteligencia (ETL)
*   **Header Hunter V4:** Algoritmo de ingesta blindado que detecta cabeceras en archivos Excel heterogéneos (formatos Ana/Andrea/SIISA), ignorando filas vacías.
*   **Maestro de CUPS Autodidacta:** El sistema "aprende" códigos nuevos al cargar archivos. Si un código no existe, lo marca como "PENDIENTE" para que el Admin lo clasifique en la vista de configuración.
*   **Normalización:** Estandarización automática de nombres de EPS y corrección de fechas.
*   **Lógica Upsert:** Evita duplicados mediante firma única (Paciente + Fecha + Procedimiento).

### 2. Gestión Operativa Avanzada
*   **Modal de Gestión Masiva XL:** Permite editar múltiples pacientes a la vez, cambiando Estado, Fecha, Prestador, Tipo de Paciente y agregando notas a la bitácora en una sola acción.
*   **WhatsApp Inteligente:** Botón "Click-to-Chat" en el perfil del paciente con plantillas predefinidas (Recordatorio, Solicitud de Documentos, Información).
*   **Bitácora (Audit Log):** Historial inmutable de gestión por usuario y fecha.
*   **Línea de Tiempo Visual:** Visualización cronológica del historial administrativo del paciente.

### 3. Módulo Clínico (Tratamientos)
*   **Robot de Ciclos (Signals):** Al crear un tratamiento (ej: Quimio cada 21 días), el sistema calcula y crea automáticamente las fechas futuras de todos los ciclos.
*   **Gestión de Adherencia:** Control de Fecha Programada vs. Fecha Real y notas clínicas por ciclo.
*   **Censo Clínico:** Reporte en tiempo real de pacientes activos por tipo de terapia.

### 4. Reportes y Salidas
*   **Tablero Operativo:** Filtros persistentes (memoria de sesión) y KPIs en tiempo real.
*   **Reportes Ejecutivos:** Exportación a Excel con estilos corporativos (OpenPyXL) y generación de Hoja de Vida del Paciente en **PDF**.
*   **Auditoría de Calidad:** Módulo técnico para detectar duplicados, registros huérfanos e inconsistencias de fechas.
*   **Alertas Proactivas:** Campana de notificaciones para casos vencidos (>30 días) y errores de datos.

---

## 🛠️ Stack Tecnológico

*   **Backend:** Python 3, Django 5.
*   **Base de Datos:** SQLite (Archivo `db.sqlite3`).
*   **Procesamiento:** Pandas (ETL), OpenPyXL (Excel), xhtml2pdf (PDF Generator).
*   **Frontend:** Bootstrap 5, Chart.js (Gráficas), FullCalendar (Agenda).
*   **Servidor:** Waitress (Producción Windows) + WhiteNoise (Archivos Estáticos).

---

## 🔐 Roles y Permisos

Gestionados desde el Admin de Django (`/admin/`):

1.  **Superusuario (Admin):**
    *   Control total.
    *   Acceso a: Auditoría de Calidad, Configuración de Maestro CUPS, Descarga de Backups, Borrado de registros.
2.  **Gestores (Equipo Operativo - Ana/Andrea):**
    *   Acceso a: Carga de Archivos, Tablero, Edición (Individual/Masiva), Gestión de Ciclos.
    *   Restricción: NO pueden borrar registros ni ver auditoría técnica.
3.  **Gerencia (Jefatura):**
    *   Acceso a: Tableros, Gráficas Gerenciales, Censo Clínico, Clasificación de CUPS.
    *   Restricción: Solo lectura en la parte operativa.

---

## ⚙️ Instalación y Despliegue

### 1. Requisitos Previos
*   Python 3.10 o superior.
*   Entorno virtual recomendado.

### 2. Instalación de Dependencias
El proyecto cuenta con un archivo `requirements.txt` que contiene todas las librerías necesarias con sus versiones exactas.

Ejecutar:
```bash
pip install -r requirements.txt
(Nota para el desarrollador: Si instalas nuevas librerías, recuerda actualizar este archivo ejecutando pip freeze > requirements.txt).

3. Configuración Inicial (Solo primera vez)
code
Bash
python manage.py migrate
python manage.py collectstatic
python manage.py createsuperuser
4. Ejecución en Producción (Red Local)
El sistema está configurado para correr en red local (LAN).
A. Configuración de IP (Obligatorio para Red):
El servidor (PC Principal) debe tener una IP Fija (ej: 192.168.1.200) configurada en Windows para que los enlaces no se rompan al reiniciar el router.
B. Arranque Automático:
El sistema incluye un script iniciar.bat y silencioso.vbs.
Colocar un acceso directo de silencioso.vbs en la carpeta shell:startup de Windows.
Esto inicia el servidor Waitress en el puerto 8000 en segundo plano al encender el PC.
C. Arranque Manual (Mantenimiento):
code
Bash
python manage.py runserver 0.0.0.0:8000
🧠 Lógica Clave (Para el Desarrollador Futuro)
1. Ingesta (followups/services.py)
Usa leer_archivo_inteligente con palabras clave para encontrar la fila de encabezados.
Usa importar_archivo_masivo con un diccionario de mapeo para normalizar columnas.
Usa calcular_procedimiento para consultar la tabla MasterCUP o inferir el tipo de servicio.
2. Ciclos (treatments/signals.py)
Se usa un post_save signal en el modelo Treatment. Si se crea un tratamiento, el signal genera los objetos Cycle automáticamente.
3. Estilos en Red (settings.py)
Se configuró mimetypes.add_type("text/css", ".css", True) para evitar que Windows bloquee los estilos CSS al acceder desde otros computadores.
⚠️ Mantenimiento y Backups
Backups: Usar el botón "Descargar Backup" en el menú lateral (solo Admin). Esto descarga el archivo .sqlite3.
Restauración: Reemplazar el archivo db.sqlite3 en la carpeta raíz con la copia de seguridad.
Reiniciar Servicio: Si el sistema se traba, buscar python.exe en el Administrador de Tareas y finalizarlo. El script de inicio (si se ejecuta de nuevo) o un reinicio del PC lo levantará.
Desarrollado para Vidanova IPS
Última actualización: Diciembre 2025