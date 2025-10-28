from django.db import models
from patients.models import Patient
from treatments.models import Treatment

class FollowUp(models.Model):
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE)
    treatment = models.ForeignKey(Treatment, on_delete=models.CASCADE)
    session_date = models.DateField()
    completed = models.BooleanField(default=False)
    interruption_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.patient.nombre} - {self.treatment.tipo} - {self.session_date}"