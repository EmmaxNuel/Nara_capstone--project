from rest_framework.views import APIView

from apps.groups.models import GroupMembership
from apps.admin_panel.audit import log_action
from utils.responses import success_response, error_response
from .models import StandingOrder
from .serializers import StandingOrderSerializer, CreateStandingOrderSerializer, PauseStandingOrderSerializer


class CreateStandingOrderView(APIView):

    def post(self, request):
        if hasattr(request.user, "standing_order"):
            return error_response("You already have an active standing order.")

        serializer = CreateStandingOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data.", errors=serializer.errors)

        standing_order = serializer.save(member=request.user)
        return success_response(
            "Standing order created.",
            data=StandingOrderSerializer(standing_order).data,
            status_code=201,
        )


class MyStandingOrderView(APIView):

    def get(self, request):
        try:
            standing_order = request.user.standing_order
        except StandingOrder.DoesNotExist:
            return error_response("No standing order found.", status_code=404)

        return success_response(
            "Standing order retrieved.",
            data=StandingOrderSerializer(standing_order).data,
        )


class PauseStandingOrderView(APIView):

    def patch(self, request):
        try:
            standing_order = request.user.standing_order
        except StandingOrder.DoesNotExist:
            return error_response("No standing order found.", status_code=404)

        if standing_order.status != "ACTIVE":
            return error_response("Only an active standing order can be paused.")

        # Prevent pausing if the member has already collected their pot —
        # pausing after collection leaves the group underfunded.
        membership = GroupMembership.objects.filter(
            member=request.user,
            group__status="ACTIVE",
        ).first()

        if membership and membership.has_collected:
            return error_response(
                "You cannot pause your standing order after collecting your pot."
            )

        serializer = PauseStandingOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data.", errors=serializer.errors)

        standing_order.status = "PAUSED"
        standing_order.pause_reason = serializer.validated_data["pause_reason"]
        standing_order.save(update_fields=["status", "pause_reason"])

        log_action(
            request.user, "STANDING_ORDER_PAUSED",
            standing_order.pause_reason,
            amount=standing_order.amount,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return success_response("Standing order paused.")


class ResumeStandingOrderView(APIView):

    def patch(self, request):
        try:
            standing_order = request.user.standing_order
        except StandingOrder.DoesNotExist:
            return error_response("No standing order found.", status_code=404)

        if standing_order.status != "PAUSED":
            return error_response("Only a paused standing order can be resumed.")

        standing_order.status = "ACTIVE"
        standing_order.pause_reason = None
        standing_order.save(update_fields=["status", "pause_reason"])

        log_action(
            request.user, "STANDING_ORDER_RESUMED",
            "Standing order resumed",
            amount=standing_order.amount,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return success_response("Standing order resumed.")
