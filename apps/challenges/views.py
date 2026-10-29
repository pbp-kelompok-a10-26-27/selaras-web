from django.contrib import messages
from django.db.models import Count, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils import timezone

from apps.core.decorators import admin_required, login_required

from .models import (
    Badge,
    Challenge,
    ChallengeParticipation,
    ChallengeProgress,
    UserBadge,
)
from .weather import get_current_weather_suggestion


def challenge_list(request):
    """List published challenges with search, filters, and weather."""

    search_query = request.GET.get("search", "").strip()

    status_filter = request.GET.get("status", "all")

    today = timezone.localdate()

    challenges = (
        Challenge.objects.filter(is_published=True)
        .annotate(participants_count=Count("participations"))
        .order_by("-created_at")
    )

    if search_query:
        challenges = challenges.filter(
            Q(title__icontains=search_query) | Q(description__icontains=search_query)
        )

    is_authenticated = hasattr(request, "user") and request.user.is_authenticated

    joined_challenge_ids = set()

    if is_authenticated:
        joined_challenge_ids = set(
            request.user.challenge_participations.values_list("challenge_id", flat=True)
        )

    if status_filter == "my" and is_authenticated:
        challenges = challenges.filter(id__in=joined_challenge_ids)

    elif status_filter == "active":
        challenges = challenges.filter(start_date__lte=today, end_date__gte=today)

    elif status_filter == "upcoming":
        challenges = challenges.filter(start_date__gt=today)

    elif status_filter == "ended":
        challenges = challenges.filter(end_date__lt=today)

    user_lat = request.GET.get("lat") or request.session.get("user_lat")

    user_lon = request.GET.get("lon") or request.session.get("user_lon")

    weather = get_current_weather_suggestion(lat=user_lat, lon=user_lon)

    if weather.get("is_custom_location"):
        request.session["user_lat"] = weather["latitude"]

        request.session["user_lon"] = weather["longitude"]

    status_options = {
        "All challenges": ["all", "layers"],
        "Active": ["active", "flame"],
        "Upcoming": ["upcoming", "calendar"],
    }

    if is_authenticated:
        status_options["My challenges"] = ["my", "user-check"]

    status_options["Ended"] = ["ended", "award"]

    label_map = {
        "all": "All challenges",
        "active": "Active",
        "upcoming": "Upcoming",
        "my": "My challenges",
        "ended": "Ended",
    }

    if status_filter not in label_map or (
        status_filter == "my" and not is_authenticated
    ):
        status_filter = "all"

    status_label = label_map[status_filter]

    context = {
        "challenges": challenges,
        "weather": weather,
        "search_query": search_query,
        "status_filter": status_filter,
        "status_options": status_options,
        "status_label": status_label,
        "joined_challenge_ids": joined_challenge_ids,
        "today": today,
        "result_count": challenges.count(),
    }

    if (
        request.headers.get("x-requested-with") == "XMLHttpRequest"
        or request.GET.get("ajax") == "1"
    ):
        html = render_to_string(
            "challenges/partials/challenge_grid.html", context, request=request
        )

        return JsonResponse(
            {
                "html": html,
                "search_query": search_query,
                "status_filter": status_filter,
                "count": challenges.count(),
            }
        )

    if request.GET.get("format") == "json":
        data = [
            {
                "id": c.id,
                "title": c.title,
                "slug": c.slug,
                "description": c.description,
                "start_date": c.start_date.isoformat(),
                "end_date": c.end_date.isoformat(),
                "is_active": c.start_date <= today <= c.end_date,
                "participants_count": c.participants_count,
                "is_joined": c.id in joined_challenge_ids,
            }
            for c in challenges
        ]

        return JsonResponse({"challenges": data, "count": len(data)})

    return render(request, "challenges/challenges.html", context)


def challenge_detail(request, slug):
    """Display challenge details, participation status, and progress."""

    challenge = get_object_or_404(Challenge, slug=slug, is_published=True)

    today = timezone.localdate()

    duration_days = max(1, (challenge.end_date - challenge.start_date).days + 1)

    is_active = challenge.start_date <= today <= challenge.end_date

    is_ended = challenge.end_date < today

    is_upcoming = challenge.start_date > today

    participation = None

    is_joined = False

    already_checked_in_today = False

    days_completed = 0

    progress_percentage = 0

    progress_records = []

    if hasattr(request, "user") and request.user.is_authenticated:
        participation = ChallengeParticipation.objects.filter(
            challenge=challenge, user=request.user
        ).first()

        if participation:
            is_joined = True

            progress_records = participation.progress_records.order_by("-progress_date")

            already_checked_in_today = progress_records.filter(
                progress_date=today
            ).exists()

            days_completed = progress_records.filter(is_completed=True).count()

            progress_percentage = min(100, int((days_completed / duration_days) * 100))

            if days_completed >= duration_days and not participation.completed_at:
                participation.completed_at = timezone.now()

                participation.save()

    context = {
        "challenge": challenge,
        "today": today,
        "duration_days": duration_days,
        "is_active": is_active,
        "is_ended": is_ended,
        "is_upcoming": is_upcoming,
        "participation": participation,
        "is_joined": is_joined,
        "already_checked_in_today": already_checked_in_today,
        "days_completed": days_completed,
        "progress_percentage": progress_percentage,
        "progress_records": progress_records,
    }

    return render(request, "challenges/challenge_detail.html", context)


@login_required
def join_challenge(request, slug):
    """Enables authenticated users to join an active challenge."""

    challenge = get_object_or_404(Challenge, slug=slug, is_published=True)

    today = timezone.localdate()

    if challenge.end_date < today:
        messages.warning(
            request, "This challenge has ended and can no longer be joined."
        )

        return redirect("challenges:detail", slug=slug)

    if challenge.start_date > today:
        messages.warning(request, "This Challenge must start before ...")

        return redirect("challenges:detail", slug=slug)

    participation, created = ChallengeParticipation.objects.get_or_create(
        challenge=challenge, user=request.user
    )

    if created:
        messages.success(
            request,
            f"You joined “{challenge.title}”.",
        )

    else:
        messages.info(request, "You already joined this challenge.")

    return redirect("challenges:detail", slug=slug)


@login_required
def leave_challenge(request, slug):
    """Enables authenticated users to cancel/leave challenge participation."""

    challenge = get_object_or_404(Challenge, slug=slug)

    if request.method == "POST":
        participation = ChallengeParticipation.objects.filter(
            challenge=challenge, user=request.user
        ).first()

        if participation:
            participation.delete()

            messages.success(
                request,
                f"You left “{challenge.title}”.",
            )

        else:
            messages.warning(request, "You have not joined this challenge.")

    next_url = request.POST.get("next")

    if next_url:
        return redirect(next_url)

    return redirect("challenges:detail", slug=slug)


@login_required
def record_progress(request, slug):
    """Record or update the daily challenge progress for the authenticated user."""

    challenge = get_object_or_404(Challenge, slug=slug, is_published=True)

    participation = get_object_or_404(
        ChallengeParticipation, challenge=challenge, user=request.user
    )

    today = timezone.localdate()

    if request.method == "POST":
        notes = request.POST.get("notes", "").strip()

        progress, created = ChallengeProgress.objects.get_or_create(
            participation=participation,
            progress_date=today,
            defaults={"notes": notes, "is_completed": True},
        )

        duration_days = max(1, (challenge.end_date - challenge.start_date).days + 1)

        days_completed = participation.progress_records.filter(
            is_completed=True
        ).count()

        if not created:
            progress.notes = notes

            progress.is_completed = True

            progress.save()

            messages.success(request, "Today’s progress note was updated.")

        else:
            if days_completed >= duration_days and not participation.completed_at:
                participation.completed_at = timezone.now()

                participation.save()

                badge, _ = Badge.objects.get_or_create(
                    name="Eco-Warrior Champion",
                    defaults={
                        "description": (
                            "Awarded for completing every day of a challenge "
                            "on SELARAS."
                        )
                    },
                )

                UserBadge.objects.get_or_create(user=request.user, badge=badge)

                messages.success(
                    request,
                    (
                        "You completed the whole challenge and earned the "
                        "Eco-Warrior Champion badge."
                    ),
                )

            else:
                messages.success(
                    request,
                    (f"Progress for {today.strftime('%B %d, %Y')} was saved."),
                )

    return redirect("challenges:detail", slug=slug)


@login_required
def challenge_history(request):
    """View user's challenge participation history, metrics, and badges."""

    tab = request.GET.get("tab", "all")

    raw_participations = (
        ChallengeParticipation.objects.filter(user=request.user)
        .select_related("challenge")
        .prefetch_related("progress_records")
        .order_by("-created_at")
    )

    participations_list = []

    total_completed = 0

    for p in raw_participations:
        duration_days = max(1, (p.challenge.end_date - p.challenge.start_date).days + 1)

        days_completed = p.progress_records.filter(is_completed=True).count()

        progress_percentage = min(100, int((days_completed / duration_days) * 100))

        is_completed = (p.completed_at is not None) or (days_completed >= duration_days)

        if is_completed:
            total_completed += 1

        p.duration_days = duration_days

        p.days_completed = days_completed

        p.progress_percentage = progress_percentage

        p.is_completed = is_completed

        participations_list.append(p)

    total_joined = len(participations_list)

    total_ongoing = total_joined - total_completed

    total_checkins = ChallengeProgress.objects.filter(
        participation__user=request.user, is_completed=True
    ).count()

    if tab == "ongoing":
        display_participations = [p for p in participations_list if not p.is_completed]

    elif tab == "completed":
        display_participations = [p for p in participations_list if p.is_completed]

    else:
        display_participations = participations_list

    user_badges = (
        UserBadge.objects.filter(user=request.user)
        .select_related("badge")
        .order_by("-awarded_at")
    )

    context = {
        "participations": display_participations,
        "total_joined": total_joined,
        "total_completed": total_completed,
        "total_ongoing": total_ongoing,
        "total_checkins": total_checkins,
        "user_badges": user_badges,
        "active_tab": tab,
    }

    return render(request, "challenges/challenge_history.html", context)


@admin_required
def challenge_create(request):
    """Redirect to the unified admin dashboard challenge creation view."""
    return redirect("dashboard:admin_challenge_create")


@admin_required
def challenge_update(request, slug):
    """Redirect to the unified admin dashboard challenge update view."""
    return redirect("dashboard:admin_challenge_update", slug=slug)


@admin_required
def challenge_delete(request, slug):
    """Redirect to the unified admin dashboard challenge list view."""
    return redirect("dashboard:admin_challenge_list")


def weather_api(request):
    """

    Internal server-side API proxy for weather recommendations.

    Accepts lat and lon query parameters, returns interpreted weather data,

    and caches coordinates in user session. Adheres to PRD Section 29.

    """

    lat = request.GET.get("lat")

    lon = request.GET.get("lon")

    weather_data = get_current_weather_suggestion(lat=lat, lon=lon)

    if weather_data.get("is_custom_location"):
        request.session["user_lat"] = weather_data["latitude"]

        request.session["user_lon"] = weather_data["longitude"]

    return JsonResponse(weather_data)
