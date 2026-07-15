from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status

from apps.members.models import Member
from apps.authentication.tests import create_verified_member
from apps.standing_orders.models import StandingOrder


class StandingOrderTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.member = create_verified_member(bank_name="GTBank", account_number="0123456789")
        self.client.force_authenticate(user=self.member)

    def test_member_can_create_a_standing_order(self):
        response = self.client.post("/api/v1/standing-orders/", {
            "bank_name": "GTBank",
            "account_number": "0123456789",
            "amount": "300000",
            "deduction_day": 25,
        })
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(StandingOrder.objects.filter(member=self.member).exists())

    def test_member_can_retrieve_their_standing_order(self):
        StandingOrder.objects.create(
            member=self.member, bank_name="GTBank", account_number="0123456789",
            amount=300000, deduction_day=25,
        )
        response = self.client.get("/api/v1/standing-orders/me/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["data"]["amount"], "300000.00")

    def test_member_cannot_create_two_standing_orders(self):
        StandingOrder.objects.create(
            member=self.member, bank_name="GTBank", account_number="0123456789",
            amount=300000, deduction_day=25,
        )
        response = self.client.post("/api/v1/standing-orders/", {
            "bank_name": "Access Bank",
            "account_number": "9876543210",
            "amount": "200000",
            "deduction_day": 25,
        })
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_unauthenticated_request_is_rejected(self):
        self.client.force_authenticate(user=None)
        response = self.client.get("/api/v1/standing-orders/me/")
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
