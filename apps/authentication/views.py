from rest_framework.views import APIView
from rest_framework.permissions import AllowAny
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.exceptions import TokenError
from rest_framework.throttling import ScopedRateThrottle

from apps.members.models import Member
from utils.responses import success_response, error_response
from .serializers import (
    RegisterSerializer,
    VerifyOTPSerializer,
    LoginSerializer,
    LogoutSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer,
)


class RegisterView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_otp"

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Registration failed.", errors=serializer.errors, status_code=400)

        member = serializer.save()
        member.is_verified = True
        member.save(update_fields=["is_verified"])

        tokens = RefreshToken.for_user(member)
        return success_response(
            "Registration successful.",
            data={
                "access": str(tokens.access_token),
                "refresh": str(tokens),
            },
            status_code=201,
        )


class VerifyOTPView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = VerifyOTPSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Verification failed.", errors=serializer.errors, status_code=400)

        phone = serializer.validated_data["phone"]
        member = Member.objects.filter(phone=phone).first()
        if not member:
            return error_response("No account found for this phone number.", status_code=404)

        member.is_verified = True
        member.save(update_fields=["is_verified"])

        tokens = RefreshToken.for_user(member)
        return success_response(
            "Phone verified successfully.",
            data={
                "access": str(tokens.access_token),
                "refresh": str(tokens),
            },
        )


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_login"

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Login failed.", errors=serializer.errors, status_code=400)

        member = serializer.validated_data["user"]
        tokens = RefreshToken.for_user(member)

        return success_response(
            "Login successful.",
            data={
                "access": str(tokens.access_token),
                "refresh": str(tokens),
            },
        )


class RefreshTokenView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get("refresh")
        if not refresh_token:
            return error_response("Refresh token is required.", status_code=400)

        try:
            token = RefreshToken(refresh_token)
            return success_response(
                "Token refreshed.",
                data={"access": str(token.access_token)},
            )
        except TokenError:
            return error_response("Invalid or expired refresh token.", status_code=401)


class LogoutView(APIView):

    def post(self, request):
        serializer = LogoutSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Logout failed.", errors=serializer.errors, status_code=400)

        try:
            token = RefreshToken(serializer.validated_data["refresh"])
            token.blacklist()
            return success_response("Logged out successfully.")
        except TokenError:
            return error_response("Invalid token.", status_code=400)


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_otp"

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Request failed.", errors=serializer.errors, status_code=400)

        phone = serializer.validated_data["phone"]
        send_otp(phone)

        return success_response("An OTP has been sent to your phone number.")


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_otp"

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if not serializer.is_valid():
            return error_response("Password reset failed.", errors=serializer.errors, status_code=400)

        phone = serializer.validated_data["phone"]
        otp = serializer.validated_data["otp"]
        new_password = serializer.validated_data["new_password"]

        is_valid = check_otp(phone, otp)
        if not is_valid:
            return error_response("Invalid or expired OTP.", status_code=400)

        member = Member.objects.filter(phone=phone).first()
        if not member:
            return error_response("No account found for this phone number.", status_code=404)

        member.set_password(new_password)
        member.save(update_fields=["password"])

        return success_response("Password reset successfully. You can now log in.")
