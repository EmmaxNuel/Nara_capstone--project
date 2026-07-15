from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.members.models import Member
from apps.authentication.tests import create_verified_member


class MemberProfileTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.member = create_verified_member()
        self.client.force_authenticate(user=self.member)

    def test_authenticated_member_can_retrieve_their_profile(self):
        response = self.client.get("/api/v1/members/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["email"], "test@nara.ng")

    def test_member_can_update_their_profile(self):
        response = self.client.patch("/api/v1/members/me/", {"full_name": "Updated Name"})
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.member.refresh_from_db()
        self.assertEqual(self.member.full_name, "Updated Name")

    def test_dashboard_returns_data_for_member_with_no_group(self):
        response = self.client.get("/api/v1/members/me/dashboard/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/members/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
