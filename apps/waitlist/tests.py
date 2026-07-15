from django.test import TestCase
from rest_framework.test import APIClient
from rest_framework import status
from unittest.mock import patch

from apps.members.models import Member
from apps.groups.models import SavingsGroup, GroupMembership
from apps.waitlist.models import Waitlist


def create_member(email="waitlister@nara.ng", phone="08077777777"):
    member = Member.objects.create_user(
        email=email, full_name="Waitlisted Person", phone=phone, password="pass123"
    )
    member.is_verified = True
    member.save()
    return member


class WaitlistTests(TestCase):

    def setUp(self):
        self.client = APIClient()
        self.member = create_member()
        self.client.force_authenticate(user=self.member)

    def test_member_is_added_to_waitlist_in_order_of_when_they_joined(self):
        self.client.post("/api/v1/waitlist/", {
            "goal_type": "CAR",
            "contribution_tier": "200000.00",
        })
        second_member = create_member(email="second@nara.ng", phone="08088880001")
        self.client.force_authenticate(user=second_member)
        self.client.post("/api/v1/waitlist/", {
            "goal_type": "CAR",
            "contribution_tier": "200000.00",
        })

        entries = Waitlist.objects.filter(goal_type="CAR", status="WAITING").order_by("priority")
        self.assertEqual(entries[0].member, self.member)
        self.assertEqual(entries[1].member, second_member)
        self.assertEqual(entries[0].priority, 1)
        self.assertEqual(entries[1].priority, 2)

    @patch("utils.termii.send_whatsapp")
    def test_highest_priority_waitlist_member_is_promoted_when_a_group_slot_opens(
        self, mock_whatsapp
    ):
        group = SavingsGroup.objects.create(
            name="Test Car Group",
            goal_type="CAR",
            contribution_tier=200000,
            max_members=4,
            status="ACTIVE",
            rotation_order=[],
        )

        Waitlist.objects.create(
            member=self.member,
            goal_type="CAR",
            contribution_tier=200000,
            priority=1,
        )

        from apps.contributions.tasks import promote_waitlist_member
        promote_waitlist_member(str(group.id))

        self.assertTrue(
            GroupMembership.objects.filter(member=self.member, group=group).exists()
        )
        entry = Waitlist.objects.get(member=self.member)
        self.assertEqual(entry.status, "PROMOTED")

    @patch("utils.termii.send_whatsapp")
    def test_promoted_waitlist_member_receives_whatsapp_message_welcoming_them_to_the_group(
        self, mock_whatsapp
    ):
        group = SavingsGroup.objects.create(
            name="WhatsApp Test Group",
            goal_type="CAR",
            contribution_tier=200000,
            max_members=4,
            status="ACTIVE",
            rotation_order=[],
        )
        Waitlist.objects.create(member=self.member, goal_type="CAR", contribution_tier=200000, priority=1)

        from apps.contributions.tasks import promote_waitlist_member
        promote_waitlist_member(str(group.id))

        mock_whatsapp.assert_called_once()
        call_args = mock_whatsapp.call_args[0]
        self.assertEqual(call_args[0], self.member.phone)

    def test_member_can_remove_themselves_from_the_waitlist_before_being_promoted(self):
        Waitlist.objects.create(
            member=self.member, goal_type="CAR", contribution_tier=200000, priority=1
        )
        response = self.client.delete("/api/v1/waitlist/")
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Waitlist.objects.filter(member=self.member, status="WAITING").exists())
