from rest_framework.views import APIView

from utils.responses import success_response, error_response
from .models import Waitlist
from .serializers import WaitlistSerializer, JoinWaitlistSerializer


class WaitlistView(APIView):

    def post(self, request):
        serializer = JoinWaitlistSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Invalid data.", errors=serializer.errors)

        data = serializer.validated_data
        member = request.user

        already_waiting = Waitlist.objects.filter(
            member=member,
            goal_type=data["goal_type"],
            contribution_tier=data["contribution_tier"],
            status="WAITING",
        ).exists()

        if already_waiting:
            return error_response("You are already on the waitlist for this goal and tier.")

        last_priority = Waitlist.objects.filter(
            goal_type=data["goal_type"],
            contribution_tier=data["contribution_tier"],
            status="WAITING",
        ).order_by("-priority").values_list("priority", flat=True).first()

        next_priority = (last_priority or 0) + 1

        entry = Waitlist.objects.create(
            member=member,
            goal_type=data["goal_type"],
            contribution_tier=data["contribution_tier"],
            priority=next_priority,
        )

        return success_response(
            "You have been added to the waitlist.",
            data=WaitlistSerializer(entry).data,
            status_code=201,
        )

    def delete(self, request):
        deleted_count, _ = Waitlist.objects.filter(
            member=request.user,
            status="WAITING",
        ).delete()

        if deleted_count == 0:
            return error_response("You are not on the waitlist.", status_code=404)

        return success_response("You have been removed from the waitlist.")


class WaitlistPositionView(APIView):

    def get(self, request):
        entry = Waitlist.objects.filter(
            member=request.user,
            status="WAITING",
        ).first()

        if not entry:
            return error_response("You are not currently on the waitlist.", status_code=404)

        return success_response(
            "Waitlist position retrieved.",
            data={
                "position": entry.priority,
                "goal_type": entry.goal_type,
                "contribution_tier": str(entry.contribution_tier),
                "joined_at": str(entry.joined_at),
            },
        )
