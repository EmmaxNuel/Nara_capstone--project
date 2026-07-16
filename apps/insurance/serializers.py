from rest_framework import serializers
from .models import InsuranceCover


class InsuranceCoverSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source="member.full_name", read_only=True)
    group_name = serializers.CharField(source="group.name", read_only=True)

    class Meta:
        model = InsuranceCover
        fields = [
            "id", "member_name", "group_name", "provider", "premium_amount",
            "coverage_amount", "start_date", "status", "claim_status",
            "claim_reason", "claim_date",
        ]
        read_only_fields = [
            "id", "provider", "premium_amount", "coverage_amount",
            "start_date", "status", "claim_status", "claim_date",
        ]


class FileClaimSerializer(serializers.Serializer):
    claim_reason = serializers.ChoiceField(choices=["DEATH", "JOB_LOSS"])
