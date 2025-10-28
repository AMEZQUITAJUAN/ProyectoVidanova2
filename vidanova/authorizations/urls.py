from rest_framework import routers
from .views import AuthorizationsViewSet

router = routers.DefaultRouter()
router.register(r'Autorizaciones', AuthorizationsViewSet)

urlpatterns = router.urls