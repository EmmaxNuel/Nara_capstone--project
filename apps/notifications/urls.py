from django.urls import path
from .views import RegisterPushTokenView

urlpatterns = [
    path("push-token/", RegisterPushTokenView.as_view(), name="register-push-token"),
]
