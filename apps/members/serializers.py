from rest_framework import serializers
from .models import Member
from utils.validators import validate_nigerian_phone, validate_account_number, validate_contribution_tier


class MemberProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = Member
        fields = [
            "id", "full_name", "email", "phone", "bank_name",
            "bank_code", "account_number", "bvn", "nin", "monthly_income",
            "contribution_tier", "savings_goal", "status",
            "is_verified", "joined_at",
        ]
        read_only_fields = ["id", "email", "phone", "is_verified", "joined_at", "status"]


class UpdateProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = Member
        fields = ["full_name", "bank_name", "bank_code", "account_number", "monthly_income"]

    def validate_account_number(self, value):
        if value:
            validate_account_number(value)
        return value
