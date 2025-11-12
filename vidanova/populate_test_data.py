#!/usr/bin/env python
"""
Script para poblar la BD con datos de prueba para verificar los gráficos.
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vidanova.settings')
django.setup()

from patients.models import Patient
from treatments.models import Treatment
from followups.models import FollowUp
from datetime import date, timedelta

def populate():
    # Limpiar datos previos (opcional)
    print("Limpiando datos previos...")
    # FollowUp.objects.all().delete()
    # Treatment.objects.all().delete()
    # Patient.objects.all().delete()

    # Crear pacientes
    print("Creando pacientes...")
    patients_data = [
        {"nombre": "Juan Pérez", "tipo_documento": "CC", "numero_documento": "12345678", "sexo": "M", "eps": "EPS Sura", "tipo_cancer": "Cáncer de pulmón"},
        {"nombre": "María García", "tipo_documento": "CC", "numero_documento": "87654321", "sexo": "F", "eps": "Nueva EPS", "tipo_cancer": "Cáncer de mama"},
        {"nombre": "Carlos López", "tipo_documento": "CC", "numero_documento": "11111111", "sexo": "M", "eps": "Salud Total", "tipo_cancer": "Cáncer de colon"},
        {"nombre": "Ana Martínez", "tipo_documento": "CC", "numero_documento": "22222222", "sexo": "F", "eps": "Caja Salud", "tipo_cancer": "Cáncer de próstata"},
        {"nombre": "Roberto Silva", "tipo_documento": "CC", "numero_documento": "33333333", "sexo": "M", "eps": "EPS Sura", "tipo_cancer": "Cáncer de páncreas"},
    ]
    
    patients = []
    for p_data in patients_data:
        p, created = Patient.objects.get_or_create(
            numero_documento=p_data["numero_documento"],
            defaults=p_data
        )
        patients.append(p)
        if created:
            print(f"  ✓ Paciente creado: {p.nombre}")
        else:
            print(f"  ℹ Paciente existente: {p.nombre}")

    # Crear tratamientos
    print("\nCreando tratamientos...")
    treatments_data = [
        {"tipo": "QMT", "observaciones": "Quimioterapia inicial"},
        {"tipo": "RX", "observaciones": "Radioterapia"},
        {"tipo": "CIR", "observaciones": "Cirugía"},
    ]
    
    treatments = []
    for t_data in treatments_data:
        for patient in patients:
            t, created = Treatment.objects.get_or_create(
                paciente=patient,
                tipo=t_data["tipo"],
                defaults={"observaciones": t_data["observaciones"]}
            )
            if created:
                treatments.append(t)
    print(f"  ✓ {len(treatments)} tratamientos creados")

    # Crear seguimientos con diferentes estados
    print("\nCreando seguimientos (FollowUps)...")
    
    today = date.today()
    states = [
        {"completed": True, "interruption_reason": "", "count": 3, "label": "Realizados"},
        {"completed": False, "interruption_reason": "agendado", "count": 2, "label": "Agendados"},
        {"completed": False, "interruption_reason": "en_gestion", "count": 2, "label": "En gestión"},
        {"completed": False, "interruption_reason": "por_gestionar", "count": 2, "label": "Por gestionar"},
        {"completed": False, "interruption_reason": "", "count": 1, "label": "Pendientes"},
    ]
    
    followup_count = 0
    for state in states:
        for i in range(state["count"]):
            patient = patients[i % len(patients)]
            treatment = Treatment.objects.filter(paciente=patient).first()
            if treatment:
                fu = FollowUp.objects.create(
                    patient=patient,
                    treatment=treatment,
                    session_date=today + timedelta(days=i),
                    completed=state["completed"],
                    interruption_reason=state["interruption_reason"]
                )
                followup_count += 1
        print(f"  ✓ {state['count']} {state['label']}")

    print(f"\n✅ Datos de prueba creados exitosamente!")
    print(f"   Total: {followup_count} seguimientos")
    print(f"   Pacientes: {len(patients)}")
    print(f"   Tratamientos: {Treatment.objects.count()}")

if __name__ == "__main__":
    populate()
