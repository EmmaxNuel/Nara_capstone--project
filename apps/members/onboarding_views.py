from rest_framework.views import APIView
from django.db import transaction

from apps.groups.models import SavingsGroup, GroupMembership
from apps.groups.matching import find_best_matching_group, member_is_already_in_active_group
from apps.standing_orders.models import StandingOrder
from apps.insurance.models import InsuranceCover
from apps.waitlist.models import Waitlist
from utils.responses import success_response, error_response
from utils.validators import validate_contribution_tier
from apps.admin_panel.audit import log_action
from apps.members.models import Member


class SaveGoalView(APIView):

    def post(self, request):
        goal = request.data.get("savings_goal")
        valid_goals = [choice[0] for choice in Member.GOAL_CHOICES]

        if not goal or goal not in valid_goals:
            return error_response(f"Invalid goal. Choose from: {', '.join(valid_goals)}")

        request.user.savings_goal = goal
        request.user.save(update_fields=["savings_goal"])
        return success_response("Savings goal saved.", data={"savings_goal": goal})


class SaveTierView(APIView):

    def post(self, request):
        tier = request.data.get("contribution_tier")
        try:
            validate_contribution_tier(tier)
        except Exception as exc:
            return error_response(str(exc))

        request.user.contribution_tier = tier
        request.user.save(update_fields=["contribution_tier"])
        return success_response("Contribution tier saved.", data={"contribution_tier": tier})


class MatchGroupView(APIView):

    def get(self, request):
        member = request.user

        if not member.savings_goal or not member.contribution_tier:
            return error_response(
                "Please complete your savings goal and contribution tier before matching.",
                status_code=400,
            )

        if member_is_already_in_active_group(member):
            return error_response("You are already a member of an active group.", status_code=400)

        group = find_best_matching_group(member.savings_goal, member.contribution_tier)

        if group:
            return success_response(
                "A matching group was found.",
                data={
                    "group_id": str(group.id),
                    "group_name": group.name,
                    "goal_type": group.goal_type,
                    "contribution_tier": str(group.contribution_tier),
                    "member_count": group.members.count(),
                    "max_members": group.max_members,
                    "monthly_pot": str(group.monthly_pot),
                    "pot_month": str(group.current_cycle_month or 1),
                    "cycle_length": group.max_members,
                },
            )

        next_priority = Waitlist.objects.filter(
            goal_type=member.savings_goal,
            contribution_tier=member.contribution_tier,
            status="WAITING",
        ).count() + 1

        waitlist_entry, created = Waitlist.objects.get_or_create(
            member=member,
            goal_type=member.savings_goal,
            contribution_tier=member.contribution_tier,
            defaults={"status": "WAITING", "priority": next_priority},
        )

        return success_response(
            "No matching group found. You can join the waitlist.",
            data={
                "waitlist": True,
                "matched": False,
                "position": waitlist_entry.priority,
            },
        )


class ConfirmGroupJoinView(APIView):

    def post(self, request):
        member = request.user
        group_id = request.data.get("group_id")

        if not group_id:
            return error_response("group_id is required.")

        if member_is_already_in_active_group(member):
            return error_response("You are already a member of an active group.")

        try:
            group = SavingsGroup.objects.get(id=group_id, status="FORMING")
        except SavingsGroup.DoesNotExist:
            return error_response("Group not found or no longer accepting members.", status_code=404)

        if group.members.count() >= group.max_members:
            return error_response("This group is already full.")

        if group.goal_type != member.savings_goal or group.contribution_tier != member.contribution_tier:
            return error_response("This group does not match your savings goal or contribution tier.")

        with transaction.atomic():
            rotation_position = group.members.count() + 1

            membership = GroupMembership.objects.create(
                member=member,
                group=group,
                rotation_position=rotation_position,
            )

            group.rotation_order.append(str(member.id))
            group.save(update_fields=["rotation_order"])

            if group.members.count() >= group.max_members:
                group.status = "ACTIVE"
                group.current_cycle_month = 1
                group.save(update_fields=["status", "current_cycle_month"])

            StandingOrder.objects.get_or_create(
                member=member,
                defaults={
                    "bank_name": member.bank_name,
                    "account_number": member.account_number,
                    "amount": member.contribution_tier,
                    "deduction_day": 25,
                },
            )

            coverage_amount = member.contribution_tier * (group.max_members - rotation_position)
            InsuranceCover.objects.get_or_create(
                member=member,
                defaults={
                    "group": group,
                    "premium_amount": member.contribution_tier * 1 / 100,
                    "coverage_amount": coverage_amount,
                },
            )

        log_action(
            member, "GROUP_JOINED",
            f"Joined group {group.name} ({group.goal_type}, ₦{group.contribution_tier})",
            amount=member.contribution_tier,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return success_response(
            "You have successfully joined the group.",
            data={
                "group_name": group.name,
                "rotation_position": rotation_position,
                "contribution_tier": str(group.contribution_tier),
            },
            status_code=201,
        )
