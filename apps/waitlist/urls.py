from django.urls import path
from .views import WaitlistView, WaitlistPositionView

urlpatterns = [
    path("", WaitlistView.as_view(), name="waitlist-join-leave"),
    path("position/", WaitlistPositionView.as_view(), name="waitlist-position"),
]
