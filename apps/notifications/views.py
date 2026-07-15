from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from utils.responses import success_response, error_response


class RegisterPushTokenView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        push_token = request.data.get("push_token")
        if not push_token:
            return error_response("push_token is required.")

        request.user.push_token = push_token
        request.user.save(update_fields=["push_token"])
        return success_response("Push token registered.")
