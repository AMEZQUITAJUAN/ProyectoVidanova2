from rest_framework import routers
from .views import TreatmentViewSet

router = routers.DefaultRouter()
router.register(r'tratamientos', TreatmentViewSet)

urlpatterns = router.urls