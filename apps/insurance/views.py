from datetime import date
from rest_framework.views import APIView

from apps.members.models import Member
from apps.standing_orders.models import StandingOrder
from apps.admin_panel.audit import log_action
from utils.responses import success_response, error_response
from .models import InsuranceCover
from .serializers import InsuranceCoverSerializer, FileClaimSerializer


class MyInsuranceCoverView(APIView):

    def get(self, request):
        try:
            cover = request.user.insurance
        except InsuranceCover.DoesNotExist:
            return error_response("No insurance cover found.", status_code=404)

        return success_response("Insurance cover retrieved.", data=InsuranceCoverSerializer(cover).data)


class FileClaimView(APIView):

    def post(self, request):
        try:
            cover = request.user.insurance
        except InsuranceCover.DoesNotExist:
            return error_response("No insurance cover found.", status_code=404)

        if cover.claim_status != "NONE":
            return error_response("A claim has already been filed for this cover.")

        serializer = FileClaimSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data.", errors=serializer.errors)

        claim_reason = serializer.validated_data["claim_reason"]

        cover.claim_status = "PENDING"
        cover.claim_reason = claim_reason
        cover.claim_date = date.today()
        cover.save(update_fields=["claim_status", "claim_reason", "claim_date"])

        # Activate 60-day grace period for job loss claims
        if claim_reason == "JOB_LOSS":
            member = request.user
            member.status = "GRACE_PERIOD"
            member.save(update_fields=["status"])

            try:
                standing_order = member.standing_order
                standing_order.status = "PAUSED"
                standing_order.pause_reason = "Insurance claim — job loss"
                standing_order.save(update_fields=["status", "pause_reason"])
            except StandingOrder.DoesNotExist:
                pass

        log_action(
            request.user, "INSURANCE_CLAIM",
            f"Claim filed — reason: {claim_reason}",
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        return success_response(
            "Claim filed successfully. Our team will review it within 48 hours.",
            data=InsuranceCoverSerializer(cover).data,
        )


class ClaimStatusView(APIView):

    def get(self, request):
        try:
            cover = request.user.insurance
        except InsuranceCover.DoesNotExist:
            return error_response("No insurance cover found.", status_code=404)

        return success_response(
            "Claim status retrieved.",
            data={
                "claim_status": cover.claim_status,
                "claim_reason": cover.claim_reason,
                "claim_date": str(cover.claim_date) if cover.claim_date else None,
            },
        )
