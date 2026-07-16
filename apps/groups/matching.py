from .models import SavingsGroup, GroupMembership


def find_best_matching_group(goal_type, contribution_tier):
    """
    Returns the FORMING group that matches goal and tier and is closest to full.
    Prioritising the fullest group means groups activate faster, which is better
    for both members (they start earning sooner) and the business (revenue starts sooner).
    Returns None if no matching group is available.
    """
    candidate_groups = SavingsGroup.objects.filter(
        goal_type=goal_type,
        contribution_tier=contribution_tier,
        status="FORMING",
    ).prefetch_related("members")

    best_group = None
    highest_member_count = -1

    for group in candidate_groups:
        current_count = len(group.members.all())
        if current_count < group.max_members and current_count > highest_member_count:
            best_group = group
            highest_member_count = current_count

    return best_group


def member_is_already_in_active_group(member):
    return GroupMembership.objects.filter(
        member=member,
        group__status__in=["FORMING", "ACTIVE"],
    ).exists()
