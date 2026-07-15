import io
from django.http import FileResponse
from rest_framework.views import APIView

from apps.groups.models import GroupMembership
from apps.admin_panel.audit import log_action
from utils.responses import success_response, error_response
from .models import Contribution
from .serializers import ContributionSerializer, ManualContributionSerializer
from .pdf import generate_contribution_statement


class ContributionListView(APIView):

    def get(self, request):
        contributions = Contribution.objects.filter(member=request.user).order_by("-created_at")
        serializer = ContributionSerializer(contributions, many=True)
        return success_response("Contributions retrieved.", data=serializer.data)


class ContributionMonthDetailView(APIView):

    def get(self, request, month_year):
        contribution = Contribution.objects.filter(
            member=request.user,
            month_year=month_year,
        ).first()

        if not contribution:
            return error_response(f"No contribution found for {month_year}.", status_code=404)

        serializer = ContributionSerializer(contribution)
        return success_response("Contribution retrieved.", data=serializer.data)


class ManualContributionView(APIView):

    def post(self, request):
        serializer = ManualContributionSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data.", errors=serializer.errors)

        data = serializer.validated_data
        member = request.user

        membership = GroupMembership.objects.filter(
            member=member,
            group_id=data["group_id"],
        ).first()

        if not membership:
            return error_response("You are not a member of this group.", status_code=403)

        if Contribution.objects.filter(
            member=member,
            group_id=data["group_id"],
            month_year=data["month_year"],
        ).exists():
            return error_response("A contribution for this month already exists.")

        contribution = Contribution.objects.create(
            member=member,
            group=membership.group,
            amount=data["amount"],
            month_year=data["month_year"],
            deduction_date=data["deduction_date"],
            method="MANUAL",
            status="PROCESSED",
        )

        log_action(
            member, "MANUAL_CONTRIBUTION",
            f"Manual contribution of ₦{data['amount']} for {data['month_year']}",
            amount=data["amount"],
            ip_address=request.META.get("REMOTE_ADDR"),
        )

        serializer = ContributionSerializer(contribution)
        return success_response("Manual contribution logged.", data=serializer.data, status_code=201)


class ContributionStatementView(APIView):

    def get(self, request):
        contributions = Contribution.objects.filter(
            member=request.user,
        ).order_by("created_at")

        pdf_buffer = generate_contribution_statement(request.user, contributions)
        return FileResponse(
            pdf_buffer,
            as_attachment=True,
            filename=f"nara_statement_{request.user.full_name.replace(' ', '_')}.pdf",
            content_type="application/pdf",
        )
