from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.authentication.tests import create_verified_member
from apps.notifications.models import Notification


class NotificationTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.member = create_verified_member()
        self.client.force_authenticate(user=self.member)

    def test_member_can_retrieve_notifications(self):
        Notification.objects.create(
            recipient=self.member, notif_type="SYSTEM",
            title="Welcome", body="Welcome to NARA!",
        )
        response = self.client.get("/api/v1/members/me/notifications/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["data"]), 1)

    def test_member_can_mark_notifications_as_read(self):
        Notification.objects.create(
            recipient=self.member, notif_type="SYSTEM",
            title="Welcome", body="Welcome to NARA!",
        )
        response = self.client.patch("/api/v1/members/me/notifications/read/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Notification.objects.filter(recipient=self.member, is_read=False).exists())

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/members/me/notifications/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
