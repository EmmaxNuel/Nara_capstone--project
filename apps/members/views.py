from rest_framework.views import APIView
from datetime import datetime
from django.db import models

from apps.notifications.models import Notification
from apps.notifications.serializers import NotificationSerializer
from apps.contributions.models import Contribution
from apps.groups.models import GroupMembership, SavingsGroup
from apps.waitlist.models import Waitlist
from apps.standing_orders.models import StandingOrder
from apps.insurance.models import InsuranceCover
from utils.responses import success_response, error_response
from .serializers import MemberProfileSerializer, UpdateProfileSerializer


class MemberProfileView(APIView):

    def get(self, request):
        m = request.user
        standing_order = StandingOrder.objects.filter(member=m).first()
        insurance = InsuranceCover.objects.filter(member=m).first()
        membership = GroupMembership.objects.filter(
            member=m,
            group__status__in=["FORMING", "ACTIVE"],
        ).select_related("group").first()

        tier_str = str(m.contribution_tier) if m.contribution_tier else None
        standing_order_info = None
        if standing_order:
            standing_order_info = f"₦{int(standing_order.amount):,}/month"

        data = {
            "full_name": m.full_name,
            "email": m.email,
            "phone": m.phone,
            "bank_name": m.bank_name or None,
            "bank_code": m.bank_code or None,
            "bank": m.bank_name or None,
            "account_number": m.account_number or None,
            "monthly_income": str(m.monthly_income) if m.monthly_income else None,
            "bvn": m.bvn or None,
            "nin": m.nin or None,
            "savings_goal": m.savings_goal or None,
            "goal": m.savings_goal or None,
            "contribution_tier": tier_str,
            "tier": tier_str,
            "joined_at": m.joined_at.isoformat() if m.joined_at else None,
            "joined_date": m.joined_at.isoformat() if m.joined_at else None,
            "standing_order_status": standing_order.status if standing_order else None,
            "standing_order_info": standing_order_info,
            "insurance_status": insurance.status if insurance else None,
            "protection_status": insurance.status if insurance else None,
            "status": m.status,
            "is_verified": m.is_verified,
            "group_name": membership.group.name if membership else None,
        }

        return success_response("Profile retrieved.", data=data)

    def patch(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)
        if not serializer.is_valid():
            return error_response("Update failed.", errors=serializer.errors)
        serializer.save()
        return success_response("Profile updated.", data=serializer.data)


class MemberDashboardView(APIView):

    def get(self, request):
        m = request.user

        membership = GroupMembership.objects.filter(
            member=m,
            group__status__in=["FORMING", "ACTIVE"],
        ).select_related("group").first()

        group_data = None
        if membership:
            group = membership.group
            total_contributed = Contribution.objects.filter(
                member=m,
                group=group,
                status="PROCESSED",
            ).count()
            total_contributed_amount = Contribution.objects.filter(
                member=m,
                group=group,
                status="PROCESSED",
            ).aggregate(total=models.Sum("amount"))["total"] or 0

            group_data = {
                "group_name": group.name,
                "goal_type": group.goal_type,
                "contribution_tier": str(group.contribution_tier),
                "monthly_pot": str(group.monthly_pot),
                "current_cycle_month": group.current_cycle_month,
                "max_members": group.max_members,
                "member_count": group.members.count(),
                "rotation_position": membership.rotation_position,
                "has_collected": membership.has_collected,
                "total_months_contributed": total_contributed,
                "total_contributed_amount": str(total_contributed_amount),
            }

        standing_order = StandingOrder.objects.filter(member=m).first()
        insurance = InsuranceCover.objects.filter(member=m).first()

        first_name = m.full_name.split()[0] if m.full_name else ""

        total_months = group_data["max_members"] if group_data else None
        current_month = group_data["current_cycle_month"] if group_data else 0
        total_contributed_amount = group_data["total_contributed_amount"] if group_data else "0"

        pot_month = None
        if group_data and current_month:
            try:
                pot_date = datetime.now().replace(day=1, hour=17, minute=0, second=0, microsecond=0)
                pot_month = pot_date.strftime("%Y-%m")
            except (ValueError, OverflowError):
                pot_month = None

        days_until_pot = None
        if group_data:
            deduction_day = standing_order.deduction_day if standing_order else 25
            now = datetime.now()
            next_deduction = now.replace(day=deduction_day, hour=6, minute=0, second=0, microsecond=0)
            if next_deduction <= now:
                if next_deduction.month == 12:
                    next_deduction = next_deduction.replace(year=next_deduction.year + 1, month=1)
                else:
                    next_deduction = next_deduction.replace(month=next_deduction.month + 1)
            days_until_pot = (next_deduction - now).days

        next_deduction_date = None
        if standing_order:
            deduction_day = standing_order.deduction_day
            now = datetime.now()
            next_deduction = now.replace(day=min(deduction_day, 28), hour=6, minute=0, second=0, microsecond=0)
            if next_deduction <= now:
                if next_deduction.month == 12:
                    next_deduction = next_deduction.replace(year=next_deduction.year + 1, month=1)
                else:
                    next_deduction = next_deduction.replace(month=next_deduction.month + 1)
            next_deduction_date = next_deduction.strftime("%Y-%m-%d")

        recent = Contribution.objects.filter(
            member=m,
        ).order_by("-created_at")[:5]

        recent_activity = []
        recent_activities = []
        for c in recent:
            entry = {
                "id": str(c.id),
                "type": "credit",
                "message": f"Contribution of ₦{int(c.amount):,} for {c.month_year}",
                "description": f"Contribution of ₦{int(c.amount):,} for {c.month_year}",
                "action": f"Contribution of ₦{int(c.amount):,} for {c.month_year}",
                "amount": str(c.amount),
                "month_year": c.month_year,
                "status": c.status,
                "created_at": c.created_at.isoformat(),
                "date": c.created_at.strftime("%d %B %Y").lstrip("0") if c.created_at else None,
                "detail": c.created_at.strftime("%d %B %Y").lstrip("0") if c.created_at else None,
            }
            recent_activity.append(entry)
            recent_activities.append(entry)

        next_ded = None
        if standing_order:
            next_ded = {
                "amount": int(standing_order.amount),
                "date": next_deduction_date,
                "bank": standing_order.bank_name,
                "bank_code": standing_order.bank_code,
                "status": standing_order.status.lower(),
            }

        return success_response(
            "Dashboard data retrieved.",
            data={
                "first_name": first_name,
                "full_name": m.full_name,
                "email": m.email,
                "phone": m.phone,
                "savings_goal": m.savings_goal,
                "goal": m.savings_goal,
                "contribution_tier": str(m.contribution_tier) if m.contribution_tier else None,
                "tier": str(m.contribution_tier) if m.contribution_tier else None,
                "total_contributed": int(float(total_contributed_amount)),
                "current_month": current_month,
                "total_months": total_months,
                "group_name": group_data["group_name"] if group_data else None,
                "pot_month": pot_month,
                "days_until_pot": days_until_pot,
                "next_deduction_date": next_deduction_date,
                "next_deduction": next_ded,
                "next_deduction_amount": str(standing_order.amount) if standing_order else "0",
                "bank_name": standing_order.bank_name if standing_order else None,
                "bank_code": standing_order.bank_code if standing_order else None,
                "bank": standing_order.bank_name if standing_order else None,
                "deduction_status": standing_order.status.lower() if standing_order else "inactive",
                "monthly_pot": int(float(group_data["monthly_pot"])) if group_data else 0,
                "member_count": group_data["member_count"] if group_data else 0,
                "recent_activity": recent_activity,
                "recent_activities": recent_activities,
            },
        )


class MemberNotificationsView(APIView):

    def get(self, request):
        notifications = Notification.objects.filter(recipient=request.user)
        serializer = NotificationSerializer(notifications, many=True)
        return success_response("Notifications retrieved.", data=serializer.data)


class MarkNotificationsReadView(APIView):

    def patch(self, request):
        updated = Notification.objects.filter(
            recipient=request.user,
            is_read=False,
        ).update(is_read=True)
        return success_response(f"{updated} notification(s) marked as read.")
