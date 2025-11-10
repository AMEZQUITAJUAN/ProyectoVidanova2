import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vidanova.settings')
django.setup()

from patients.models import Patient
from treatments.models import Treatment
from followups.models import FollowUp
from datetime import date, timedelta

def create_test_data():
    # Crear algunos pacientes de prueba
    patient1 = Patient.objects.create(
        nombre="Juan Pérez",
        tipo_documento="CC",
        numero_documento="12345678",
        fecha_nacimiento="1980-01-01",
        sexo="M",
        eps="EPS Sura",
        tipo_cancer="Cáncer de pulmón"
    )

    patient2 = Patient.objects.create(
        nombre="María García",
        tipo_documento="CC",
        numero_documento="87654321",
        fecha_nacimiento="1990-05-15",
        sexo="F",
        eps="Nueva EPS",
        tipo_cancer="Cáncer de mama"
    )

    # Crear algunos tratamientos de prueba
    treatment1 = Treatment.objects.create(
        paciente=patient1,
        tipo="QMT",
        fecha_inicio=date.today() - timedelta(days=30),
        fecha_fin=date.today() + timedelta(days=60),
        estado="activo",
        observaciones="Quimioterapia inicial"
    )

    treatment2 = Treatment.objects.create(
        paciente=patient2,
        tipo="RX",
        fecha_inicio=date.today(),
        fecha_fin=date.today() + timedelta(days=45),
        estado="activo",
        observaciones="Radioterapia programada"
    )

    # Crear seguimientos (followups)
    FollowUp.objects.create(
        patient=patient1,
        treatment=treatment1,
        session_date=date.today(),
        completed=True,
        interruption_reason=""
    )

    FollowUp.objects.create(
        patient=patient1,
        treatment=treatment2,
        session_date=date.today() + timedelta(days=7),
        completed=False,
        interruption_reason="por_gestionar"
    )

    FollowUp.objects.create(
        patient=patient2,
        treatment=treatment1,
        session_date=date.today() - timedelta(days=3),
        completed=True,
        interruption_reason=""
    )

    print("Datos de prueba creados exitosamente!")
    print("\nPacientes creados:")
    for patient in Patient.objects.all():
        print(f"- {patient.nombre}")
    
    print("\nTratamientos creados:")
    for treatment in Treatment.objects.all():
        print(f"- {treatment.tipo} para {treatment.paciente.nombre}")
    
    print("\nSeguimientos creados:")
    for followup in FollowUp.objects.all():
        print(f"- Paciente: {followup.patient.nombre}, Tratamiento: {followup.treatment.tipo}, Completado: {followup.completed}")

if __name__ == "__main__":
    create_test_data()