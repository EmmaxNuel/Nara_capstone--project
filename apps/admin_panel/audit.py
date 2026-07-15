from .models import AuditLog


def log_action(member, action, description, amount=None, ip_address=None):
    AuditLog.objects.create(
        member=member,
        action=action,
        amount=amount,
        description=description,
        ip_address=ip_address,
    )
