# vidanova/followups/management/commands/import_followups.py
import os
import pandas as pd
from datetime import datetime
from django.conf import settings
from django.core.management.base import BaseCommand
from followups.models import FollowUp
from patients.models import Patient

class Command(BaseCommand):
    help = "Importa pacientes y seguimientos desde media/uploads/processed_latest.csv"

    def handle(self, *args, **kwargs):
        csv_path = os.path.join(settings.MEDIA_ROOT, "uploads", "processed_latest.csv")

        if not os.path.exists(csv_path):
            self.stdout.write(self.style.ERROR(f"No se encontró el archivo: {csv_path}"))
            return

        # Leer CSV
        df = pd.read_csv(csv_path)
        df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]

        self.stdout.write(f"Columnas detectadas: {list(df.columns)}")
        self.stdout.write("Importando datos, por favor espera...")

        FollowUp.objects.all().delete()
        Patient.objects.all().delete()

        for _, row in df.iterrows():
            # Crear o actualizar el paciente
            numero_doc = str(row.get("identificación") or row.get("identificacion") or "").strip()
            if not numero_doc:
                continue

            patient, _ = Patient.objects.get_or_create(
                numero_documento=numero_doc,
                defaults={
                    "tipo_documento": _map_doc_type(row.get("tipo_de_identificación", "CC")),
                    "nombre_1": row.get("nombre_1", ""),
                    "nombre_2": row.get("nombre_2", ""),
                    "apellido_1": row.get("apellido_1", ""),
                    "apellido_2": row.get("apellido_2", ""),
                    "correo": row.get("correo", ""),
                    "genero": row.get("genero", ""),
                    "edad": _parse_int(row.get("edad")),
                    "ocupacion": row.get("ocupación", ""),
                    "escolaridad": row.get("escolaridad", ""),
                    "departamento_residencia": row.get("departamento_de_residencia", ""),
                    "ciudad_residencia": row.get("ciudad_de_residencia", ""),
                    "estado_natural": row.get("estado_natural", ""),
                },
            )

            # Crear el seguimiento asociado
            FollowUp.objects.create(
                patient=patient,
                fecha_atencion=_parse_date(row.get("fecha_de_atención")),
                entidad_aseguradora=row.get("entidad_asegurdora"),
                cups=row.get("cups"),
                servicio=row.get("servicio"),
                tipo=row.get("tipo"),
                grupo=row.get("grupo"),
                cantidad=_parse_int(row.get("cantidad")),
                observaciones=row.get("observaciones"),
                prioridad_atencion=row.get("prioridad_atención"),
                ubicacion=row.get("ubicacion"),
                profesional=row.get("profesional"),
                especialidad=row.get("especialidad"),
                codigo_grupo_diagnostico=row.get("codigo_grupo_diagnostico"),
                grupo_diagnostico=row.get("grupo_diagnostico"),
                codigo_diagnostico=row.get("codigo_diagnostico"),
                diagnostico=row.get("diagnostico"),
                ubicacion_diagnostico=row.get("ubicación_diagnostico"),
                tipo_estadificacion_dx=row.get("tipo_estadificacion_dx"),
                estadificacion_diagnostico=row.get("estadificacion_diagnóstico"),
                tipo_paciente=row.get("tipo_de_paciente"),
                fecha_captacion=_parse_date(row.get("fecha_de__captación") or row.get("fecha_de_captacion")),
                tipo_procedimiento=row.get("tipo_de_procedimiento"),
                estado_solicitud=row.get("estado_de_solicitud"),
                fecha_solicitud_cita=_parse_date(row.get("fecha_de_solicitud_de_cita")),
                fecha_cita=_parse_date(row.get("fecha_de_cita")),
                prestador=row.get("prestador"),
                barrera=row.get("barrera"),
                oportunidad=row.get("oportunidad"),
                ruta=row.get("ruta"),
                mes_ordenamiento=row.get("mes_de_ordenamiento"),
                semana_ordenamiento=row.get("semana_de_ordenamiento"),
            )

        self.stdout.write(self.style.SUCCESS(f"Importación completada: {len(df)} registros importados."))


# 🧩 Funciones auxiliares
def _parse_date(value):
    """Convierte fechas con varios formatos (dd/mm/yyyy o yyyy-mm-dd)"""
    if not value or pd.isna(value):
        return None
    value = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%Y/%m/%d"):
        try:
            return datetime.strptime(value, fmt).date()
        except ValueError:
            continue
    return None


def _parse_int(value):
    """Convierte texto numérico a entero"""
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return None


def _map_doc_type(value):
    """Normaliza el tipo de documento"""
    val = str(value).upper()
    if "CEDULA" in val:
        return "CC"
    if "TARJETA" in val:
        return "TI"
    if "EXTRANJERIA" in val:
        return "CE"
    return "CC"
