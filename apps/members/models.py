import uuid
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from .managers import MemberManager


class Member(AbstractBaseUser, PermissionsMixin):

    GOAL_CHOICES = [
        ("LAND", "Land"),
        ("CAR", "Car"),
        ("HOUSE", "House"),
        ("BUSINESS", "Business Capital"),
        ("SCHOOL_FEES", "School Fees"),
        ("FLEXIBLE", "Flexible"),
    ]

    STATUS_CHOICES = [
        ("ACTIVE", "Active"),
        ("GRACE_PERIOD", "Grace Period"),
        ("SUSPENDED", "Suspended"),
        ("GRADUATED", "Graduated"),
        ("WAITLISTED", "Waitlisted"),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=150)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=14, unique=True)
    bank_name = models.CharField(max_length=100, blank=True)
    bank_code = models.CharField(max_length=10, blank=True, default="")
    account_number = models.CharField(max_length=10, blank=True)
    bvn = models.CharField(max_length=11, blank=True)
    nin = models.CharField(max_length=11, blank=True)
    monthly_income = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    contribution_tier = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    savings_goal = models.CharField(max_length=20, choices=GOAL_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="ACTIVE")
    push_token = models.CharField(max_length=255, blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    joined_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name", "phone"]

    objects = MemberManager()

    class Meta:
        db_table = "members"
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.full_name} ({self.email})"
