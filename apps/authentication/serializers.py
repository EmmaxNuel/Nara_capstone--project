from rest_framework import serializers
from django.contrib.auth import authenticate
from apps.members.models import Member
from utils.validators import validate_nigerian_phone


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = Member
        fields = ["full_name", "email", "phone", "password", "bank_name", "account_number", "bvn", "nin"]

    def validate_email(self, value):
        if Member.objects.filter(email=value).exists():
            raise serializers.ValidationError("A member with this email already exists.")
        return value

    def validate_phone(self, value):  # noqa: F811
        validate_nigerian_phone(value)
        if Member.objects.filter(phone=value).exists():
            raise serializers.ValidationError("A member with this phone number already exists.")
        return value

    def create(self, validated_data):
        return Member.objects.create_user(**validated_data)


class VerifyOTPSerializer(serializers.Serializer):
    phone = serializers.CharField()
    otp = serializers.CharField(min_length=6, max_length=6)


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        user = authenticate(email=data["email"], password=data["password"])
        if not user:
            raise serializers.ValidationError("Invalid email or password.")
        if not user.is_verified:
            raise serializers.ValidationError("Please verify your phone number before logging in.")
        if not user.is_active:
            raise serializers.ValidationError("This account has been deactivated.")
        data["user"] = user
        return data


class LogoutSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class ForgotPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField()

    def validate_phone(self, value):
        validate_nigerian_phone(value)
        if not Member.objects.filter(phone=value).exists():
            raise serializers.ValidationError("No account found with this phone number.")
        return value


class ResetPasswordSerializer(serializers.Serializer):
    phone = serializers.CharField()
    new_password = serializers.CharField(write_only=True, min_length=8)
