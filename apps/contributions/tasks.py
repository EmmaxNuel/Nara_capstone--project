from celery import shared_task
from celery.utils.log import get_task_logger
from datetime import date, timedelta
import calendar

from utils.flutterwave import initiate_debit, initiate_transfer, verify_transaction
from utils.termii import send_sms, send_whatsapp

logger = get_task_logger(__name__)


@shared_task(bind=True, max_retries=3)
def process_monthly_deductions(self):
    """Runs on the 25th of every month at 6am Lagos time."""
    from apps.standing_orders.models import StandingOrder
    from apps.contributions.models import Contribution

    today = date.today()
    month_year = today.strftime("%Y-%m")
    active_orders = StandingOrder.objects.filter(status="ACTIVE").select_related("member")

    for order in active_orders:
        member = order.member
        reference = f"NARA-DED-{member.id}-{month_year}"

        contribution, created = Contribution.objects.get_or_create(
            member=member,
            group=member.memberships.filter(group__status="ACTIVE").first().group,
            month_year=month_year,
            defaults={
                "amount": order.amount,
                "deduction_date": today,
                "status": "PENDING",
                "method": "STANDING_ORDER",
                "transaction_ref": reference,
            },
        )

        if not created:
            continue

        response = initiate_debit(
            account_number=order.account_number,
            bank_code="",
            amount=order.amount,
            narration=f"NARA savings contribution — {month_year}",
            reference=reference,
        )

        if response and response.get("status") == "success":
            transaction_id = response.get("data", {}).get("id")
            verified = verify_transaction(transaction_id) if transaction_id else False
            contribution.status = "PROCESSED" if verified else "FAILED"
        else:
            contribution.status = "FAILED"

        contribution.save(update_fields=["status"])

        if contribution.status == "PROCESSED":
            order.last_executed = today
            order.save(update_fields=["last_executed"])
            update_reserve_fund.delay(str(contribution.group.id), float(contribution.amount))
            send_sms(
                member.phone,
                f"Hi {member.full_name}, your NARA contribution of ₦{order.amount:,.0f} for {month_year} has been deducted. Keep saving!",
            )
        else:
            send_sms(
                member.phone,
                f"Hi {member.full_name}, your NARA contribution deduction for {month_year} failed. Please ensure your account has sufficient funds.",
            )

    logger.info("Monthly deductions processed for %s", month_year)


@shared_task(bind=True, max_retries=3)
def check_failed_deductions(self):
    """Runs every day at 9am — reminds members with failed contributions."""
    from apps.contributions.models import Contribution

    seven_days_ago = date.today() - timedelta(days=7)

    failed_contributions = Contribution.objects.filter(
        status="FAILED",
        created_at__date__gte=seven_days_ago,
    ).select_related("member")

    for contribution in failed_contributions:
        member = contribution.member
        send_sms(
            member.phone,
            f"Hi {member.full_name}, your NARA contribution for {contribution.month_year} is still unpaid. "
            f"Please contact us or make a manual payment to keep your slot.",
        )

        consecutive_failures = Contribution.objects.filter(
            member=member,
            status="FAILED",
        ).order_by("-created_at")[:3].count()

        if consecutive_failures >= 3:
            member.status = "SUSPENDED"
            member.save(update_fields=["status"])
            logger.warning("Member %s flagged for review after 3 consecutive failed deductions.", member.email)


def _is_last_day_of_month():
    today = date.today()
    return today.day == calendar.monthrange(today.year, today.month)[1]


@shared_task(bind=True, max_retries=3)
def trigger_pot_disbursement(self):
    """Runs every day at 5pm — only executes on the last day of the month."""
    if not _is_last_day_of_month():
        return
    from apps.groups.models import SavingsGroup
    from apps.contributions.models import Contribution
    from apps.disbursements.models import PotDisbursement
    from apps.groups.models import GroupMembership
    from apps.notifications.models import Notification

    today = date.today()
    month_year = today.strftime("%Y-%m")
    active_groups = SavingsGroup.objects.filter(status="ACTIVE")

    for group in active_groups:
        pending_exists = Contribution.objects.filter(
            group=group,
            month_year=month_year,
            status="PENDING",
        ).exists()

        if pending_exists:
            logger.info("Skipping disbursement for group %s — pending contributions exist.", group.name)
            continue

        if PotDisbursement.objects.filter(group=group, month_year=month_year).exists():
            continue

        collector = group.current_collector
        if not collector:
            logger.warning("No collector found for group %s in %s", group.name, month_year)
            continue

        amount = group.monthly_pot
        reference = f"NARA-DISB-{group.id}-{month_year}"

        transfer_response = initiate_transfer(
            account_number=collector.account_number,
            bank_code="",
            amount=amount,
            narration=f"NARA pot — {month_year}",
            reference=reference,
        )

        status = "PROCESSED" if transfer_response else "FAILED"
        bank_ref = transfer_response.get("data", {}).get("id") if transfer_response else None

        PotDisbursement.objects.create(
            group=group,
            recipient=collector,
            amount=amount,
            month_year=month_year,
            disbursement_date=today,
            status=status,
            bank_reference=str(bank_ref) if bank_ref else None,
        )

        if status == "PROCESSED":
            GroupMembership.objects.filter(member=collector, group=group).update(has_collected=True)

            group.current_cycle_month += 1
            if group.current_cycle_month > group.max_members:
                group.status = "COMPLETE"
            group.save(update_fields=["current_cycle_month", "status"])

            send_whatsapp(
                collector.phone,
                f"Congratulations {collector.full_name}! Your NARA pot of ₦{amount:,.0f} has been sent to your account. Enjoy!",
            )

            all_members = GroupMembership.objects.filter(group=group).select_related("member")
            for membership in all_members:
                Notification.objects.create(
                    recipient=membership.member,
                    notif_type="POT_MONTH",
                    title="Monthly Pot Disbursed",
                    body=f"The pot of ₦{amount:,.0f} for {month_year} has been sent to {collector.full_name}.",
                    channel="IN_APP",
                )


@shared_task
def send_deduction_reminders():
    """Runs 3 days before each member's deduction day."""
    from apps.standing_orders.models import StandingOrder


    today = date.today()
    target_day = (today + timedelta(days=3)).day

    upcoming_orders = StandingOrder.objects.filter(
        status="ACTIVE",
        deduction_day=target_day,
    ).select_related("member")

    for order in upcoming_orders:
        deduction_date = today + timedelta(days=3)
        send_whatsapp(
            order.member.phone,
            f"Hi {order.member.full_name}, your NARA contribution of ₦{order.amount:,.0f} "
            f"will be deducted on {deduction_date.strftime('%d %B %Y')}. "
            f"Please ensure your account is funded.",
        )


@shared_task
def update_reserve_fund(group_id, contribution_amount):
    """Called after every successful contribution. Adds 2% to the group reserve fund."""
    from apps.groups.models import SavingsGroup
    from django.db.models import F
    from decimal import Decimal

    # 2% of every contribution is set aside to cover members who miss payments
    reserve_addition = Decimal(str(contribution_amount)) * Decimal("0.02")

    SavingsGroup.objects.filter(id=group_id).update(
        reserve_fund=F("reserve_fund") + reserve_addition
    )


@shared_task
def check_grace_periods():
    """Runs every day at 8am — checks if any 60-day grace period has expired."""
    from apps.members.models import Member
    from apps.insurance.models import InsuranceCover

    grace_members = Member.objects.filter(status="GRACE_PERIOD")

    for member in grace_members:
        try:
            cover = member.insurance
        except InsuranceCover.DoesNotExist:
            continue

        if not cover.claim_date:
            continue

        days_elapsed = (date.today() - cover.claim_date).days

        if days_elapsed >= 60:
            promote_waitlist_member.delay(
                str(member.memberships.filter(group__status="ACTIVE").first().group.id)
            )


@shared_task
def promote_waitlist_member(group_id):
    """Promotes the highest-priority waitlist member when a group slot opens."""
    from apps.groups.models import SavingsGroup, GroupMembership
    from apps.waitlist.models import Waitlist


    try:
        group = SavingsGroup.objects.get(id=group_id)
    except SavingsGroup.DoesNotExist:
        return

    next_candidate = Waitlist.objects.filter(
        goal_type=group.goal_type,
        contribution_tier=group.contribution_tier,
        status="WAITING",
    ).order_by("priority").first()

    if not next_candidate:
        logger.info("No waitlist candidates for group %s", group.name)
        return

    member = next_candidate.member
    rotation_position = group.members.count() + 1

    GroupMembership.objects.create(
        member=member,
        group=group,
        rotation_position=rotation_position,
    )

    group.rotation_order.append(str(member.id))
    group.save(update_fields=["rotation_order"])

    next_candidate.status = "PROMOTED"
    next_candidate.save(update_fields=["status"])

    send_whatsapp(
        member.phone,
        f"Welcome to NARA, {member.full_name}! You have been promoted from the waitlist "
        f"and added to the group '{group.name}'. Your contribution of ₦{group.contribution_tier:,.0f} "
        f"starts next month. We're glad to have you!",
    )

    logger.info("Waitlist member %s promoted to group %s", member.email, group.name)


@shared_task
def match_waitlisted_members():
    """Runs daily — tries to match waitlisted members to available FORMING groups."""
    from apps.waitlist.models import Waitlist
    from apps.groups.matching import find_best_matching_group, member_is_already_in_active_group

    combinations = Waitlist.objects.filter(
        status="WAITING",
    ).values_list("goal_type", "contribution_tier").distinct()

    for goal_type, contribution_tier in combinations:
        group = find_best_matching_group(goal_type, contribution_tier)
        while group:
            candidate = Waitlist.objects.filter(
                goal_type=goal_type,
                contribution_tier=contribution_tier,
                status="WAITING",
            ).order_by("priority").first()

            if not candidate:
                break

            if member_is_already_in_active_group(candidate.member):
                candidate.status = "CANCELLED"
                candidate.save(update_fields=["status"])
                candidate = Waitlist.objects.filter(
                    goal_type=goal_type,
                    contribution_tier=contribution_tier,
                    status="WAITING",
                ).order_by("priority").first()
                if not candidate:
                    break

            promote_waitlist_member(str(group.id))

            slot_remaining = group.members.count() < group.max_members
            if not slot_remaining:
                break
