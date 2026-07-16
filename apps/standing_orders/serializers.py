from rest_framework import serializers
from .models import StandingOrder
from utils.validators import validate_account_number


class StandingOrderSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)

    class Meta:
        model = StandingOrder
        fields = [
            "id", "member_name", "bank_name", "bank_code", "account_number", "amount",
            "deduction_day", "status", "activation_date", "last_executed", "pause_reason",
        ]
        read_only_fields = ["id", "activation_date", "last_executed", "status"]

    def validate_account_number(self, value):
        validate_account_number(value)
        return value

    def validate_deduction_day(self, value):
        if not (1 <= value <= 28):
            raise serializers.ValidationError("Deduction day must be between 1 and 28.")
        return value


class CreateStandingOrderSerializer(serializers.ModelSerializer):

    class Meta:
        model = StandingOrder
        fields = ["bank_name", "bank_code", "account_number", "amount", "deduction_day"]

    def validate_account_number(self, value):
        validate_account_number(value)
        return value

    def validate_deduction_day(self, value):
        if not (1 <= value <= 28):
            raise serializers.ValidationError("Deduction day must be between 1 and 28.")
        return value


class PauseStandingOrderSerializer(serializers.Serializer):
    pause_reason = serializers.CharField(max_length=255)
