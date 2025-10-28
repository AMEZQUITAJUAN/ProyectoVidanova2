from rest_framework import routers
from .views import PatientViewSet

router = routers.DefaultRouter()
router.register(r'pacientes', PatientViewSet)

urlpatterns = router.urls