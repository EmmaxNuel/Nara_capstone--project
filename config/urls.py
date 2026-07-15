from django.contrib import admin
from django.urls import path, include


urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/auth/", include("apps.authentication.urls")),
    path("api/v1/members/", include("apps.members.urls")),
    path("api/v1/onboarding/", include("apps.members.onboarding_urls")),
    path("api/v1/groups/", include("apps.groups.urls")),
    path("api/v1/contributions/", include("apps.contributions.urls")),
    path("api/v1/standing-orders/", include("apps.standing_orders.urls")),
    path("api/v1/disbursements/", include("apps.disbursements.urls")),
    path("api/v1/insurance/", include("apps.insurance.urls")),
    path("api/v1/waitlist/", include("apps.waitlist.urls")),
    path("api/v1/notifications/", include("apps.notifications.urls")),
]
