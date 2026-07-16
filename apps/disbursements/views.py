from datetime import date
from rest_framework.views import APIView
from rest_framework.permissions import IsAdminUser

from apps.groups.models import GroupMembership
from apps.contributions.models import Contribution
from apps.admin_panel.audit import log_action
from utils.responses import success_response, error_response
from utils.flutterwave import initiate_transfer
from .models import PotDisbursement
from .serializers import PotDisbursementSerializer


class DisbursementListView(APIView):

    def get(self, request):
        membership = GroupMembership.objects.filter(
            member=request.user,
            group__status__in=["FORMING", "ACTIVE", "COMPLETE"],
        ).select_related("group").first()

        if not membership:
            return error_response("You are not in any group.", status_code=404)

        disbursements = PotDisbursement.objects.filter(group=membership.group)
        serializer = PotDisbursementSerializer(disbursements, many=True)
        return success_response("Disbursements retrieved.", data=serializer.data)


class ProcessDisbursementView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        from apps.groups.models import SavingsGroup

        group_id = request.data.get("group_id")
        if not group_id:
            return error_response("group_id is required.")

        try:
            group = SavingsGroup.objects.get(id=group_id, status="ACTIVE")
        except SavingsGroup.DoesNotExist:
            return error_response("Active group not found.", status_code=404)

        month_year = date.today().strftime("%Y-%m")

        pending_contributions = Contribution.objects.filter(
            group=group,
            month_year=month_year,
            status="PENDING",
        ).exists()

        if pending_contributions:
            return error_response(
                "Cannot disburse — some contributions for this month are still pending."
            )

        collector = group.current_collector
        if not collector:
            return error_response("No collector found for the current month.")

        if PotDisbursement.objects.filter(group=group, month_year=month_year).exists():
            return error_response("Disbursement for this month has already been processed.")

        amount = group.monthly_pot
        reference = f"NARA-DISB-{group.id}-{month_year}"

        transfer_response = initiate_transfer(
            account_number=collector.account_number,
            bank_code=collector.bank_code,
            amount=amount,
            narration=f"NARA pot disbursement — {month_year}",
            reference=reference,
        )

        status = "PROCESSED" if transfer_response else "FAILED"
        bank_ref = transfer_response.get("data", {}).get("id") if transfer_response else None

        disbursement = PotDisbursement.objects.create(
            group=group,
            recipient=collector,
            amount=amount,
            month_year=month_year,
            disbursement_date=date.today(),
            status=status,
            bank_reference=str(bank_ref) if bank_ref else None,
        )

        if status == "PROCESSED":
            membership = GroupMembership.objects.filter(member=collector, group=group).first()
            if membership:
                membership.has_collected = True
                membership.save(update_fields=["has_collected"])

            group.current_cycle_month += 1
            if group.current_cycle_month > group.max_members:
                group.status = "COMPLETE"
            group.save(update_fields=["current_cycle_month", "status"])

        log_action(
            collector, "POT_DISBURSEMENT",
            f"Pot disbursed ₦{amount} for {month_year} to {collector.full_name}. Status: {status}",
            amount=amount,
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        serializer = PotDisbursementSerializer(disbursement)
        return success_response(
            f"Disbursement {status.lower()}.",
            data=serializer.data,
            status_code=201,
        )
