import uuid
from django.db import models
from apps.members.models import Member


class StandingOrder(models.Model):

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("PAUSED", "Paused"),
        ("CANCELLED", "Cancelled"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    member = models.OneToOneField(Member, on_delete=models.CASCADE, related_name="standing_order")
    bank_name = models.CharField(max_length=100)
    bank_code = models.CharField(max_length=10, blank=True, default="")
    account_number = models.CharField(max_length=10)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    deduction_day = models.PositiveIntegerField()  # Day of month salary is expected
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    activation_date = models.DateField(auto_now_add=True)
    last_executed = models.DateField(null=True, blank=True)
    pause_reason = models.CharField(max_length=255, blank=True, null=True)

    class Meta:
        db_table = "standing_orders"

    def __str__(self):
        return f"{self.member.full_name} — ₦{self.amount} on day {self.deduction_day}"
